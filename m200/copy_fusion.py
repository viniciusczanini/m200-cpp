"""Fuse unique private copies without moving observable reads across effects."""

import re
from collections import Counter
from .model import fail
from .edges import SERIES
from .numeric import is_operation
from .indexed import has_indexed

WORD_ASSIGN = re.compile(r"\[\s*(%(?:MW|MD|MF)[0-9]+|%TM[0-9]+\.P)\s*:=\s*(.*?)\s*\]")
PURE_BIT = re.compile(r"%(?:M[0-9]+|I0\.[0-9]+|Q0\.[0-9]+|S(?:13|20)|MW[0-9]+:X[0-9]+)")


def fuse(program, registers, members, groups, reference, live_out):
    def owner(ref):
        return members.get(ref, (ref, 0))[0]

    def refs(rung):
        return Counter(owner(ref) for line in rung for ref in reference.findall(line))

    counts = refs([line for rung in program.rungs for line in rung])
    direct_register_snapshots = not (
        program.subroutines
        or has_indexed(program)
        or any(
            re.search(r"%MW[0-9]+:X[0-9]+", line)
            for rung in program.rungs
            for line in rung
        )
    )

    def temporary(ref, bank):
        reg = registers.get(ref)
        return (
            reg is not None
            and owner(ref) == ref
            and not reg.persistent
            and ref not in groups
            and reg.bank == bank
            and reg.width == (1 if reg.kind in ("bool", "i16") else 2)
        )

    def pure(value):
        return value in ("0", "1") or PURE_BIT.fullmatch(value) is not None

    def bits(line):
        parts = line.split(maxsplit=1)
        return parts if len(parts) == 2 else ("", "")

    def bounded(rung):
        if not all(bits(line)[0] in SERIES for line in rung[:-1]):
            return True
        width = sum(2 if bits(line)[1].startswith("[") else 1 for line in rung[:-1])
        return width <= (9 if is_operation(rung[-1]) else 10)

    def combine(a, b, end):
        if not a or not b or a[0].startswith("%L") or b[0].startswith("%L"):
            return None
        if direct_register_snapshots and len(a) == len(b) == 2 and a[0] == "LD 1":
            definition = WORD_ASSIGN.fullmatch(a[1])
            if definition:
                temp, source = definition.groups()
                if (
                    temporary(temp, "word")
                    and registers[temp].kind == "i16"
                    and counts[temp] == 2
                    and re.fullmatch(r"%R[0-3]\.(?:I|O)", source)
                    and re.fullmatch(
                        r"LD \[\s*"
                        + re.escape(temp)
                        + r"\s*(?:>=|<=|<>|=|>|<)\s*-?[0-9]+\s*\]",
                        b[0],
                    )
                    and b[1].startswith("ST ")
                ):
                    # A direct i16 Register read has no flag/index effects. Move
                    # its single evaluation into the immediately following
                    # comparison, with no mutation/label/guard between them.
                    return [b[0].replace(temp, source), b[1]]
        # Forward the one read into the next rung's initial load. It is still
        # evaluated exactly once, before that rung's other effects.
        if len(a) == 2:
            load, source = bits(a[0])
            store, temp = bits(a[1])
            next_load, value = bits(b[0])
            if (
                load in ("LD", "LDN", "LDR", "LDF")
                and store == "ST"
                and next_load == "LD"
                and value == temp
                and temporary(temp, "bit")
                and (
                    counts[temp] == 2
                    or (temp not in live_out[end] and refs(b)[temp] == 1)
                )
            ):
                replacement = [a[0]] + b[1:]
                if bounded(replacement):
                    return replacement
        # A terminal ST fully defines a private scalar; a following direct
        # copy can retarget that ST when there are no other alias uses.
        if len(b) == 2:
            first, target = bits(a[-1])
            load, value = bits(b[0])
            store, dest = bits(b[1])
            if (
                first == "ST"
                and load == "LD"
                and store == "ST"
                and value == target
                and "[" not in dest
                and temporary(target, "bit")
                and (
                    counts[target] == 2
                    or (target not in live_out[end] and refs(b)[target] == 1)
                )
            ):
                return a[:-1] + ["ST " + dest]
        # A captured private guard is stable across this comparison and ST.
        # G AND (G AND P) needs one evaluation of P, in the original position.
        # Flag/system/word-bit guards and shared/partial stores are excluded.
        if len(a) == 3 and len(b) == 3:
            load, guard = bits(a[0])
            predicate_op, predicate = bits(a[1])
            store, temp = bits(a[2])
            next_load, next_guard = bits(b[0])
            operator, value = bits(b[1])
            last, dest = bits(b[2])
            if (
                load == next_load == "LD"
                and guard == next_guard
                and temporary(guard, "bit")
                and guard != temp
                and predicate_op == operator == "AND"
                and predicate.startswith("[")
                and predicate.endswith("]")
                and store == last == "ST"
                and value == temp
                and temporary(temp, "bit")
                and (
                    counts[temp] == 2
                    or (temp not in live_out[end] and refs(b)[temp] == 1)
                )
            ):
                # Operands still have virtual addresses at this stage. Keep
                # the comparison verbatim; final validation checks its type,
                # physical bounds and existing indexed-contact restrictions.
                replacement = a[:-1] + ["ST " + dest]
                if bounded(replacement):
                    return replacement
        if len(a) == 2 and len(b) == 2 and a[0] == b[0]:
            load, guard = bits(a[0])
            definition = WORD_ASSIGN.fullmatch(a[1])
            copy = WORD_ASSIGN.fullmatch(b[1])
            if load == "LD" and pure(guard) and definition and copy:
                temp, expression = definition.groups()
                target, value = copy.groups()
                reg = registers.get(temp)
                target_kind = (
                    "i16"
                    if target.startswith(("%MW", "%TM"))
                    else "i32"
                    if target.startswith("%MD")
                    else "f32"
                )
                if (
                    value == temp
                    and temporary(temp, "word")
                    and reg.kind == target_kind
                    and (
                        counts[temp] == 2
                        or (temp not in live_out[end] and refs(b)[temp] == 1)
                    )
                ):
                    return [a[0], "[" + target + ":=" + expression + "]"]
        # Suppressing/reordering an indexed or numeric read could change S20
        # or arithmetic errors. Fold NOT only when BOTH reads are pure bits.
        if len(a) == 2 and len(b) == 3:
            load, source = bits(a[0])
            store, temp = bits(a[1])
            second, left = bits(b[0])
            operator, right = bits(b[1])
            if (
                load == "LDN"
                and store == "ST"
                and second in ("LD", "LDN")
                and operator in ("AND", "ANDN")
                and right == temp
                and temporary(temp, "bit")
                and counts[temp] == 2
                and pure(source)
                and pure(left)
            ):
                return [b[0], ("ANDN " if operator == "AND" else "AND ") + source, b[2]]
        # Keep the last definition of a private boolean while holding the
        # accumulator across pure series contacts; no intermediate alias read.
        if len(a) >= 2 and len(b) >= 2:
            store, target = bits(a[-1])
            load, value = bits(b[0])
            last, dest = bits(b[-1])
            series = all(
                bits(line)[0]
                in ("LD", "LDN", "LDR", "LDF", "AND", "ANDN", "ANDR", "ANDF")
                for line in a[:-1]
            )
            pure_tail = all(
                bits(line)[0] in ("AND", "ANDN") and pure(bits(line)[1])
                for line in b[1:-1]
            )
            merged = a[:-1] + b[1:]
            width = sum(
                2 if bits(line)[1].startswith("[") else 1 for line in merged[:-1]
            )
            if (
                store == "ST"
                and load == "LD"
                and last == "ST"
                and value == target == dest
                and temporary(target, "bit")
                and refs(b)[target] == 2
                and series
                and pure_tail
                and width <= 10
            ):
                return merged
        return None

    origins = program.metadata.get("rung_origins")
    if origins is not None and (
        not isinstance(origins, list) or len(origins) != len(program.rungs)
    ):
        fail("invalid source map metadata")
    stack = []
    mapped = []
    ends = []
    eliminated = 0
    before = sum(map(len, program.rungs))
    for i, rung in enumerate(program.rungs):
        stack.append(rung)
        mapped.append(origins[i] if origins is not None else None)
        ends.append(i)
        while len(stack) >= 2:
            a, b = stack[-2:]
            replacement = combine(a, b, ends[-1])
            if replacement is None:
                break
            counts.subtract(refs(a))
            counts.subtract(refs(b))
            counts.update(refs(replacement))
            stack[-2:] = [replacement]
            mapped[-2:] = [mapped[-2]]
            ends[-2:] = [ends[-1]]
            eliminated += 1
    if not eliminated:
        return
    dead = {
        root
        for root, reg in registers.items()
        if not reg.persistent and root not in groups and counts[root] == 0
    }
    for root in dead:
        del registers[root]
    for ref, (root, _) in list(members.items()):
        if root in dead:
            members.pop(ref)
            program.symbols.pop(ref, None)
    program.rungs = stack
    if origins is not None:
        program.metadata["rung_origins"] = mapped
    program.metadata["copy_fusion"] = {
        "eliminated_rungs": eliminated,
        "instructions_before": before,
        "instructions_after": sum(map(len, stack)),
        "method": "private scalars with unique uses or CFG dead-after proof; alias owners; equal numeric guards; pure-bit NOT folding; bounded columns; no label crossing",
    }
