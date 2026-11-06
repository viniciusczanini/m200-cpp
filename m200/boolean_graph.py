"""Native expression-edge series graph and documented resource limits.

RisingEdgeBlock/Descriptor=index is observed in the pinned public T source.
Both block tokens occur in installed Entities.dll metadata. Falling block
layout follows that same series shape; official save/reopen remains pending.
"""
from .edge_functions import parse as expression_edge
from .edges import contact_type
from .flow import split_label
from .levels import functional_level
from .model import fail
from .boolean_banks import config


def expression_series(raw):
    _,lines = split_label(raw)
    if len(lines) != 3:
        return None
    first,last = lines[0].split(maxsplit=1),lines[2].split(maxsplit=1)
    edge = expression_edge(lines[1])
    if edge is None or len(first)!=2 or first[0] not in ("LD","LDN","LDR","LDF") or len(last)!=2 or last[0] not in ("ST","S","R"):
        return None
    if first[1].startswith("[") or first[1] in ("0","1"):
        return None
    return first,edge,last


def graphics(raw):
    value = expression_series(raw)
    if value is None:
        return None
    first,(kind,index),last = value
    return [(contact_type(first[0]),first[1],0),
            ("RisingEdgeBlock" if kind=="RISING" else "FallingEdgeBlock",str(index),1)] + [
                ("Line","",i) for i in range(2,10)
            ] + [({"ST":"Coil","S":"SetCoil","R":"ResetCoil"}[last[0]],last[1],10)]


def validate_profile(program,token):
    # The expanded implementation has its own M/instruction overhead and does
    # not claim to allocate native expression function objects.
    if not config(program).native_expression_edges:
        return
    level = functional_level(token)
    maximum = 255 if level >= (10,1) else 32
    seen = {"RISING":set(),"FALLING":set()}
    contexts = [program.rungs] + [v.rungs for v in program.subroutines.values()]
    for rungs in contexts:
        for raw in rungs:
            for line in raw:
                op = line.split(maxsplit=1)[0]
                edge = expression_edge(op)
                if edge:
                    if level < (6,0):
                        fail("native expression edges require functional level >=6.0")
                    kind,index = edge
                    if index >= maximum or index in seen[kind]:
                        fail(f"native {kind} identity exceeds per-kind limit{maximum} or is duplicated")
                    seen[kind].add(index)
