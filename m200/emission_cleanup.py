"""Remove proved private no-ops while virtual ownership is still available."""

from collections import Counter
import re

from .indexed import has_indexed
from .edges import OPS as EDGE_OPS
from .model import fail

COPY = re.compile(r"\[\s*(%MW[0-9]+)\s*:=\s*(%MW[0-9]+)\s*\]")
SHARED_VIEW = re.compile(r"%M(?:[0-9]+:[0-9]+|W[0-9]+:X[0-9]+)")


def cleanup(program, registers, members, groups, names, constants, reference):
    # Indirect reads can observe a scratch cell or depend on the direct image
    # extent, even when no ordinary reference reads it. Keep their old emission.
    if (
        program.subroutines
        or has_indexed(program)
        or any(SHARED_VIEW.search(line) for rung in program.rungs for line in rung)
    ):
        return
    origins = program.metadata.get("rung_origins")
    if origins is not None and (
        not isinstance(origins, list) or len(origins) != len(program.rungs)
    ):
        fail("invalid source map metadata")

    def private(ref, kind):
        reg = registers.get(ref)
        return (
            reg is not None
            and reg.kind == kind
            and reg.width == 1
            and not reg.persistent
            and ref not in groups
            and members.get(ref) == (ref, 0)
        )

    def drop(indices):
        nonlocal origins
        indices = set(indices)
        program.rungs = [r for i, r in enumerate(program.rungs) if i not in indices]
        if origins is not None:
            origins = [o for i, o in enumerate(origins) if i not in indices]
            program.metadata["rung_origins"] = origins

    copies = []
    for i, rung in enumerate(program.rungs):
        if len(rung) != 2:
            continue
        load = rung[0].split(maxsplit=1)
        assignment = COPY.fullmatch(rung[1])
        if (
            len(load) != 2
            or load[0] != "LD"
            or not private(load[1], "bool")
            or assignment is None
        ):
            continue
        dest, source = assignment.groups()
        if (
            private(dest, "i16")
            and private(source, "i16")
            and names[dest] == names[source]
        ):
            copies.append(i)
    # Do this first so an adjacent label anchor can attach to the real body,
    # rather than making an otherwise removable copy into a jump target.
    drop(copies)

    references = Counter(
        ref
        for rung in program.rungs
        for line in rung
        for ref in reference.findall(line)
    )
    false_loads = {"LD 0"}
    if "0" in constants:
        false_loads.add("LD " + constants["0"])
    # Native M-edge history belongs to the physical cell, not a virtual root.
    # An unread scratch can still share a cell sampled by such an edge.
    memory_edges = any(
        len(parts) == 2
        and parts[0] in EDGE_OPS
        and re.fullmatch(r"%M[0-9]+", parts[1])
        for rung in program.rungs
        for line in rung
        for parts in [line.split(maxsplit=1)]
    )
    candidates = {}
    for i, rung in enumerate(program.rungs):
        if (
            not memory_edges
            and len(rung) == 3
            and re.fullmatch(r"%L(?:0|[1-9][0-9]*):", rung[0])
            and rung[1] in false_loads
            and rung[2].startswith("ST ")
        ):
            target = rung[2][3:]
            if private(target, "bool"):
                candidates[i] = target
    stores = Counter(candidates.values())
    anchors, label_origins = [], {}
    for i, target in candidates.items():
        if references[target] != stores[target] or i + 1 == len(program.rungs):
            continue
        following = program.rungs[i + 1]
        if following[0].split(maxsplit=1)[0] not in ("LD", "LDN"):
            continue
        label = program.rungs[i][0]
        following.insert(0, label)
        anchors.append(i)
        if origins is not None:
            label_origins[label[:-1]] = origins[i]
    dropped_targets = {candidates[i] for i in anchors}
    drop(anchors)
    used = {
        ref
        for rung in program.rungs
        for line in rung
        for ref in reference.findall(line)
    }
    for target in dropped_targets - used:
        registers.pop(target)
        for ref, (owner, _) in list(members.items()):
            if owner == target:
                members.pop(ref)
                program.symbols.pop(ref, None)
    if copies or anchors:
        program.metadata["emission_cleanup"] = {
            "private_i16_self_copies": len(copies),
            "label_anchors": len(anchors),
            "label_origins": label_origins,
            "method": "post-allocation physical identity plus virtual ownership; direct private scalars; no indexed/shared views or SR",
        }
