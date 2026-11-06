"""Native timer block grammar, independent of graphical/evidence admission."""

import re
from .model import fail


def index(text):
    match = re.fullmatch(r"%TM(0|[1-9][0-9]*)", text)
    if match is None or int(match[1]) >= 255:
        fail("invalid native timer address: " + text)
    return int(match[1])


def body(rung):
    """Qualify local IN/Q names; OUT_BLK and output wiring are optional.

    Repeated block visits/sites are execution order, not additional resources.
    This parser never substitutes a disabled IN for a skipped block.
    """
    rung = [" ".join(line.split()) for line in rung]
    if not rung or not rung[0].startswith("BLK %TM"):
        return None
    target = rung[0].split(maxsplit=1)[1]
    index(target)
    if (
        rung[-1] != "END_BLK"
        or any(line.startswith("BLK ") for line in rung[1:])
        or rung.count("END_BLK") != 1
        or rung.count("IN") != 1
        or rung.count("OUT_BLK") > 1
    ):
        fail("invalid timer block structure; composed blocks require separate rungs")
    at = rung.index("IN")
    out = rung.index("OUT_BLK") if "OUT_BLK" in rung else len(rung) - 1
    if at < 2 or out != at + 1:
        fail("timer requires one IN before its optional output section")
    result = rung[1:at] + ["IN " + target]
    # Before IN only Boolean evaluation is legal. The shared decoder checks
    # operands, stack balance and all unsupported instruction names afterwards.
    allowed = {
        "LD", "LDN", "LDR", "LDF", "AND", "ANDN", "ANDR", "ANDF",
        "OR", "ORN", "ORR", "ORF", "XOR", "XORN", "XORR", "XORF",
        "AND(", "OR(", "N", ")", "MPS", "MRD", "MPP",
    }
    for line in rung[1:at]:
        op = line.split(maxsplit=1)[0]
        if op not in allowed and not re.fullmatch(r"(?:RISING|FALLING)[0-9]+", op):
            fail("unsupported timer input instruction: " + line)
    outputs = rung[out + 1:-1] if out < len(rung) - 1 else []
    if outputs and outputs[0] not in ("LD Q", "LDN Q"):
        fail("timer output section must begin by loading Q")
    for line in outputs:
        parts = line.split(maxsplit=1)
        op = parts[0]
        if op in ("BLK", "END_BLK", "OUT_BLK", "IN", "JMP", "JMPC", "JMPCN", "END", "ENDC", "ENDCN"):
            fail("unsupported timer output instruction: " + line)
        if len(parts) == 2 and parts[1] == "Q":
            if op not in allowed:
                fail("timer Q is read-only")
            line = op + " " + target + ".Q"
        result.append(line)
    return result
