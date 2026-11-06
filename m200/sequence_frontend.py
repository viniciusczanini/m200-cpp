"""Frontend adapter for native DR/SBR/SC; keeps family changes out of core AST code."""
import re
from .model import fail
from .numeric import Number, boolean
from .sequences import FAMILIES, CLASSES, CONFIGS, PINS, DrumConfig, DrumCam

BY_CLASS = {v: k for k, v in CLASSES.items()}


def constructor(front, node, kind):
    from .frontend import walk
    ctor = next((n for n in node.get("inner", []) if n.get("kind") in ("CXXConstructExpr", "CXXTemporaryObjectExpr")), None)
    if ctor is None:
        front.error(node, "native sequence requires an explicit constructor")
    args = ctor.get("inner", [])
    family = BY_CLASS[kind]
    if len(args) < (2 if family == "DR" else 1) or (family != "DR" and len(args) != 1):
        front.error(node, "invalid native sequence constructor arguments")
    index = front.const(args[0])
    if type(index) is not int or not 0 <= index < 8:
        front.error(node, "native sequence index must be 0..7")
    if family != "DR":
        return family, index, CONFIGS[family]()
    cams = []
    for arg in args[2:]:
        cam = next((n for n in walk(arg) if n.get("kind") in ("CXXConstructExpr", "CXXTemporaryObjectExpr") and n.get("type", {}).get("qualType") == "plc::DrumCam" and len(n.get("inner", [])) == 4), None)
        if cam is None or len(cam.get("inner", [])) != 4:
            front.error(arg, "Drum requires literal plc::DrumCam records")
        slot, bank, address, mask = [front.const(v) for v in cam["inner"]]
        if bank not in (0, 1):
            front.error(arg, "invalid DrumOutput bank")
        cams.append(DrumCam(slot, ("%M" if bank == 0 else "%Q0.") + str(address), mask))
    return family, index, DrumConfig(front.const(args[1]), cams)


def declare(front, node, kind):
    family, index, cfg = constructor(front, node, kind)
    configs = getattr(front.lower.program, FAMILIES[family])
    if index in configs:
        front.error(node, "duplicate native sequence identity")
    configs[index] = cfg
    front.instances[node["id"]] = (kind, index)


def expression(front, node, ref, member, args, env):
    kind, index = front.instances[ref]
    family = BY_CLASS[kind]
    key = "%" + family + str(index)
    method = member.get("name")
    if method in ("bit", "step", "full"):
        if method == "bit" and family != "DR" and len(args) == 1:
            bit = front.index(args[0], 16 if family == "SBR" else 256, node)
            return front.lower.copy(key + "." + str(bit), "sequence_bit")
        if family == "DR" and not args and method in ("step", "full"):
            return front.lower.copy(Number("i16", key + ".S") if method == "step" else key + ".F", "drum_property")
        front.error(node, "invalid native sequence getter")
    if front.active:
        front.error(node, "stateful sequence calls are not allowed in pure helpers")
    if method == "set_bit" and family != "DR" and len(args) == 2:
        bit = front.index(args[0], 16 if family == "SBR" else 256, node)
        front.lower.assign(key + "." + str(bit), boolean(front.expr(args[1], env)), front.lower.guard)
        return None
    if method == "set_step" and family == "DR" and len(args) == 1:
        value = front.const(args[0])
        if not 0 <= value <= 7:
            front.error(node, "Drum set_step requires decimal immediate 0..7")
        front.lower.assign(Number("i16", key + ".S"), Number("i16", str(value)), front.lower.guard)
        return None
    if method not in ("update", "update_pins"):
        front.error(node, "unsupported native sequence method")
    pins = PINS[family]
    mask = (1 << len(pins)) - 1
    if method == "update_pins":
        if not args:
            front.error(node, "sequence update_pins requires a literal presence mask")
        mask = front.const(args[0])
        args = args[1:]
    if not 1 <= mask < 1 << len(pins) or len(args) != len(pins):
        front.error(node, "invalid sequence pin mask/argument count")
    # Capture arguments in source order, including unused-mask arguments. Pure
    # reads may have diagnostics and must not vanish merely because a pin is absent.
    signals = []
    for arg in args:
        value = boolean(front.expr(arg, env))
        signals.append(value if re.fullmatch(r"%I0\.[0-9]+", value) else front.lower.copy(value, "sequence_argument"))
    end = None
    if front.lower.guard is not None:
        end = front.lower.new_label()
        front.lower.jump(end, front.lower.guard, negate=True)
    lines = ["BLK " + key]
    for i, pin in enumerate(pins):
        if mask & (1 << i):
            lines += ["LD " + signals[i], pin]
    front.lower.rung(*lines, "END_BLK")
    if end is not None:
        front.lower.label(end)
    return None
