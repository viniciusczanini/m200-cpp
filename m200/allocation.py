"""Allocate compiler-private storage using CFG liveness, never user addresses.

Globals and instance state retain unique cells. Explicit addresses and complete
communication buffers remain reserved even if the program never reads them.
Conditional writes do not kill the previous value in the liveness equations.
"""

import re
from collections import deque
from dataclasses import dataclass

from .flow import JUMPS, destinations, split_label
from .model import fail
from .numeric import Number, TYPES
from .edges import OPS as EDGE_OPS
from .edge_functions import parse as expression_edge
from .copy_fusion import fuse as fuse_copies
from .dead_stores import eliminate as eliminate_dead_stores
from .emission_cleanup import cleanup as cleanup_emission

REFERENCE = re.compile(r"%M(?:W|D|F)?[0-9]+")
ASSIGNMENT = re.compile(
    r"(?:OPER\s+)?\[\s*(%M(?:W|D|F)[0-9]+|%R[0-9]+\.(?:I|O)|%(?:TM|C)[0-9]+\.P|%(?:M[0-9]+|Q0\.[0-9]+):[0-9]+)(?:\[%MW[0-9]+\])?\s*:="
)
UNARY = re.compile(r"(?:OPER\s+)?\[\s*(?:INC|DEC)\s+(%M(?:W|D)[0-9]+)\s*\]")


@dataclass(frozen=True)
class Register:
    kind: str
    width: int
    persistent: bool

    @property
    def bank(self):
        return "bit" if self.kind == "bool" else "word"


def known_bit(arg, constants):
    if arg in ("0", "1"):
        return arg == "1"
    return constants.get(arg)


def effects(rung, registers, constants, aliases=None):
    """Return aggregate and per-instruction effects, plus the final accumulator."""
    reads, definitions, writes = set(), set(), set()
    steps = []
    aliases = aliases or {}

    def owner(ref):
        return aliases.get(ref, (ref, 0))[0]

    acc = None
    for line in rung:
        parts = line.split(maxsplit=1)
        op, arg = parts[0], parts[1] if len(parts) == 2 else ""
        refs = [r for r in REFERENCE.findall(line) if owner(r) in registers]
        target = None
        must = False
        unary = UNARY.fullmatch(line)
        assignment = ASSIGNMENT.match(line)
        if not (assignment or unary or expression_edge(op) is not None) and op not in (
            "LD",
            "LDN",
            "AND",
            "ANDN",
            "OR",
            "ORN",
            "XOR",
            "XORN",
            *EDGE_OPS,
            "ST",
            "S",
            "R",
            *JUMPS,
            "BLK",
            "IN",
            "CU",
            "CD",
            "OUT_BLK",
            "END_BLK",
            "EXECUTE",
            "ABORT",
            "I",
            "O",
        ):
            fail("unmodelled instruction effects in memory allocation: " + line)
        if op in ("ST", "S", "R"):
            target = arg.split("[", 1)[0].split(":X", 1)[0]
            must = op == "ST" or acc is True
            if target in refs:
                refs.remove(target)
        elif assignment or unary:
            target = (assignment or unary)[1]
            must = acc is True
            if assignment and target in refs:
                refs.remove(target)
        indexed_target = (
            "[" in arg
            if op in ("ST", "S", "R")
            else bool(assignment and "[" in assignment[0].partition("[")[2])
        )
        if target is not None:
            target = owner(target)
        refs = [owner(ref) for ref in refs]
        if target in registers:
            element_width = (
                1
                if registers[target].kind == "bool"
                else TYPES[registers[target].kind][1]
            )
            must = (
                must
                and ":X" not in arg
                and not indexed_target
                and registers[target].width == element_width
            )
        reads.update(ref for ref in refs if ref not in definitions)
        line_reads, line_definitions, line_writes = set(refs), set(), set()
        if target in registers and (op == "ST" or acc is not False):
            writes.add(target)
            line_writes.add(target)
            if must:
                definitions.add(target)
                line_definitions.add(target)
        steps.append((line_reads, line_definitions, line_writes))
        if op in EDGE_OPS or expression_edge(op) is not None:
            acc = None
        elif op in ("LD", "LDN"):
            acc = known_bit(arg, constants)
            if op == "LDN" and acc is not None:
                acc = not acc
        elif op in ("AND", "ANDN", "OR", "ORN", "XOR", "XORN"):
            value = known_bit(arg, constants)
            if op.endswith("N") and value is not None:
                value = not value
            if op.startswith("AND"):
                acc = (
                    False
                    if acc is False or value is False
                    else (True if acc is True and value is True else None)
                )
            elif op.startswith("OR"):
                acc = (
                    True
                    if acc is True or value is True
                    else (False if acc is False and value is False else None)
                )
            else:
                acc = acc != value if acc is not None and value is not None else None
        elif op == "BLK":
            acc = None
    return reads, definitions, writes, acc, steps


def live_ranges(program, registers, constants, aliases=None):
    count = len(program.rungs)
    if not count:
        return [], []
    labels = destinations(program)
    uses, defs, steps, successors = [], [], [], []
    for index, raw in enumerate(program.rungs):
        _, rung = split_label(raw)
        use, defined, _, acc, instructions = effects(
            rung, registers, constants, aliases
        )
        uses.append(use)
        defs.append(defined)
        steps.append(instructions)
        op, *args = rung[-1].split(maxsplit=1)
        following = (index + 1) % count  # state can remain live between scans
        if op in JUMPS:
            target = labels[args[0]]
            take = (
                True
                if op == "JMP"
                else acc
                if op == "JMPC"
                else (not acc if acc is not None else None)
            )
            successors.append(
                {target}
                if take is True
                else {following}
                if take is False
                else {target, following}
            )
        else:
            successors.append({following})
    predecessors = [set() for _ in range(count)]
    for i, targets in enumerate(successors):
        for target in targets:
            predecessors[target].add(i)
    live = [set() for _ in range(count)]
    pending = deque(reversed(range(count)))
    queued = set(pending)
    while pending:
        index = pending.popleft()
        queued.remove(index)
        out = set().union(*(live[s] for s in successors[index]))
        incoming = uses[index] | (out - defs[index])
        if incoming != live[index]:
            live[index] = incoming
            for previous in predecessors[index] - queued:
                pending.append(previous)
                queued.add(previous)
    return steps, [set().union(*(live[s] for s in successors[i])) for i in range(count)]


def interference(program, registers, constants, aliases=None):
    graph = {ref: set() for ref in registers}
    steps, live_out = live_ranges(program, registers, constants, aliases)
    for i, instructions in enumerate(steps):
        out = live_out[i]
        for read, defined, written in reversed(instructions):
            for target in written:
                for other in out:
                    if (
                        other != target
                        and registers[other].bank == registers[target].bank
                    ):
                        graph[target].add(other)
                        graph[other].add(target)
            out = (out - defined) | read
    return graph


class Storage:
    def __init__(self, reserved_bits=(), reserved_words=()):
        self.reserved = {"bit": set(reserved_bits), "word": set(reserved_words)}
        self.registers = {}
        self.members = {}
        self.groups = set()
        self.next_bit = 100000
        self.next_word = 100000

    def bit(self, symbol, persistent=False):
        code = "%M" + str(self.next_bit)
        self.next_bit += 1
        self.registers[code] = Register("bool", 1, persistent)
        self.members[code] = (code, 0)
        return code

    def word(self, kind, symbol, persistent=False):
        prefix, width = TYPES[kind]
        code = "%" + prefix + str(self.next_word)
        self.next_word += width
        self.registers[code] = Register(kind, width, persistent)
        self.members[code] = (code, 0)
        return Number(kind, code)

    def array(self, kind, count, symbol, persistent=False):
        prefix, stride = ("M", 1) if kind == "bool" else TYPES[kind]
        cursor = self.next_bit if kind == "bool" else self.next_word
        root = "%" + prefix + str(cursor)
        self.groups.add(root)
        self.registers[root] = Register(kind, count * stride, persistent)
        values = []
        for i in range(count):
            code = "%" + prefix + str(cursor + i * stride)
            self.members[code] = (root, i * stride)
            values.append(code if kind == "bool" else Number(kind, code))
        if kind == "bool":
            self.next_bit += count
        else:
            self.next_word += count * stride
        return values

    def word_bit(self, value, bit):
        root, offset = self.members[value.code]
        alias = "%MW" + str(int(value.code[3:]) + bit // 16)
        self.members[alias] = (root, offset + bit // 16)
        return alias + ":X" + str(bit % 16)

    def finalize(self, program, constants):
        fusible = {
            ref: reg
            for ref, reg in self.registers.items()
            if not reg.persistent and ref not in self.groups
        }
        if not program.subroutines:
            _, out = live_ranges(
                program,
                fusible,
                {v: k == "1" for k, v in constants.items()},
                self.members,
            )
            removed = eliminate_dead_stores(
                program, self.registers, self.members, self.groups, REFERENCE, out
            )
            if removed:
                fusible = {
                    ref: reg for ref, reg in fusible.items() if ref in self.registers
                }
                _, out = live_ranges(
                    program,
                    fusible,
                    {v: k == "1" for k, v in constants.items()},
                    self.members,
                )
            fuse_copies(
                program, self.registers, self.members, self.groups, REFERENCE, out
            )
        fixed = {bank: set(cells) for bank, cells in self.reserved.items()}
        mapping = {}

        def choose(ref, forbidden):
            reg = self.registers[ref]
            capacity = 1024 if reg.bank == "bit" else 8000
            for base in range(capacity - reg.width + 1):
                if all(i not in forbidden for i in range(base, base + reg.width)):
                    return base
            fail(
                f"{reg.bank} memory allocation does not fit the target and compiler storage; "
                "conservative allocation/overhead is not proof that no native implementation fits"
            )

        for ref, reg in self.registers.items():
            if reg.persistent:
                base = choose(ref, fixed[reg.bank])
                mapping[ref] = base
                fixed[reg.bank].update(range(base, base + reg.width))
        temporary = {
            ref: reg for ref, reg in self.registers.items() if not reg.persistent
        }
        if program.subroutines:
            # No single-stream liveness/fusion may reuse a caller value across
            # a native call. Initial prototype gives same-bank temporaries unique
            # storage across every execution context.
            graph = {
                ref: {
                    other
                    for other, candidate in temporary.items()
                    if other != ref and candidate.bank == reg.bank
                }
                for ref, reg in temporary.items()
            }
        else:
            graph = interference(
                program,
                temporary,
                {v: k == "1" for k, v in constants.items()},
                self.members,
            )
        ordinal = {ref: i for i, ref in enumerate(temporary)}
        for ref in sorted(
            temporary, key=lambda r: (-len(graph[r]), -temporary[r].width, ordinal[r])
        ):
            reg = temporary[ref]
            forbidden = set(fixed[reg.bank])
            for other in graph[ref]:
                if other in mapping:
                    base = mapping[other]
                    forbidden.update(range(base, base + temporary[other].width))
            mapping[ref] = choose(ref, forbidden)
        names = {
            ref: ref.rstrip("0123456789") + str(mapping[root] + offset)
            for ref, (root, offset) in self.members.items()
        }

        cleanup_emission(
            program,
            self.registers,
            self.members,
            self.groups,
            names,
            constants,
            REFERENCE,
        )

        def rewrite(text):
            return REFERENCE.sub(lambda m: names.get(m[0], m[0]), text)

        program.rungs = [[rewrite(line) for line in rung] for rung in program.rungs]
        for definition in program.subroutines.values():
            definition.rungs = [
                [rewrite(line) for line in rung] for rung in definition.rungs
            ]
        owners = {bank: {} for bank in fixed}
        for ref, reg in self.registers.items():
            for cell in range(mapping[ref], mapping[ref] + reg.width):
                owners[reg.bank].setdefault(cell, set()).add(ref)
        reused = set().union(
            *(
                refs
                for cells in owners.values()
                for refs in cells.values()
                if len(refs) > 1
            )
        )
        symbols = {}
        for ref, name in program.symbols.items():
            physical = names.get(ref, ref)
            symbols[physical] = (
                "compiler_reused_" + physical[1:]
                if self.members.get(ref, (ref, 0))[0] in reused
                else name
            )
        program.symbols = symbols
        program.metadata["allocation"] = {
            "virtual_bits": sum(
                r.width for r in self.registers.values() if r.bank == "bit"
            ),
            "virtual_words": sum(
                r.width for r in self.registers.values() if r.bank == "word"
            ),
            "allocated_bits": len(
                {
                    i
                    for k, r in self.registers.items()
                    if r.bank == "bit"
                    for i in range(mapping[k], mapping[k] + r.width)
                }
            ),
            "allocated_words": len(
                {
                    i
                    for k, r in self.registers.items()
                    if r.bank == "word"
                    for i in range(mapping[k], mapping[k] + r.width)
                }
            ),
            "reserved_bits": len(self.reserved["bit"]),
            "reserved_words": len(self.reserved["word"]),
            "contiguous_groups": len(self.groups),
            "method": "conservative unique cross-context scratch; globals/explicit addresses reserved"
            if program.subroutines
            else "conservative CFG liveness; globals unique; explicit addresses and communication buffers reserved",
        }
        if (
            sum(map(len, program.rungs))
            + sum(
                sum(map(len, definition.rungs))
                for definition in program.subroutines.values()
            )
            > 10000
        ):
            fail("experimental instruction budget exceeded after optimization")
        return program
