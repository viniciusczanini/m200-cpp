"""Use the isolated MAST task's native I/Q process images directly."""

import re


Q = re.compile(r"%Q0\.(\d+)(?::(\d+))?")
ASSIGN = re.compile(r"\[\s*(%Q0\.\d+(?::\d+)?)\s*:=\s*(.*?)\s*\]")


def refs(text):
    return {
        i
        for m in Q.finditer(text)
        for i in range(int(m[1]), int(m[1]) + int(m[2] or 1))
    }


def initialization(rungs, channels, constants):
    """Conservatively retain RUN initialization unless a write dominates use.

    Branches, labels, END and native blocks retain initialization. A simple
    straight-line body can prove its first full write before any output read.
    """
    required = set(channels)
    if any(
        line.startswith("%L")
        or line.split(maxsplit=1)[0]
        in ("JMP", "JMPC", "JMPCN", "END", "ENDC", "ENDCN", "BLK")
        for rung in rungs
        for line in rung
    ):
        return required
    pending = set(required)
    for rung in rungs:
        acc = None
        for line in rung:
            parts = line.split(maxsplit=1)
            op, arg = parts[0], parts[1] if len(parts) == 2 else ""
            assignment = ASSIGN.fullmatch(line)
            written = set()
            if op in ("ST", "STN", "S", "R"):
                read = set()
                if op in ("ST", "STN"):
                    written = refs(arg)
            elif assignment:
                read = refs(assignment[2])
                if acc is True:
                    written = refs(assignment[1])
            else:
                read = refs(line)
            pending -= read
            proven = written & pending
            required -= proven
            pending -= proven
            if op in ("LD", "LDN"):
                acc = arg == "1" if arg in ("0", "1") else constants.get(arg)
                if op == "LDN" and acc is not None:
                    acc = not acc
            elif op not in ("ST", "STN", "S", "R"):
                acc = None
    return required


def reset_rungs(channels):
    remaining = set(channels)
    result = []
    while remaining:
        start = min(remaining)
        count = 1
        if start % 8 == 0:
            while count < 16 and start + count in remaining:
                count += 1
        if count > 1:
            result.append(["LD %S13", f"[%Q0.{start}:{count}:=0]"])
        else:
            result.append(["LD %S13", f"R %Q0.{start}"])
        remaining -= set(range(start, start + count))
    return result
