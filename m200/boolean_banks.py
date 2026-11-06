"""Boolean operand domains and explicit image contract (G01).

G = EIO0000003289.04 pp20,27,39-48; P = EIO0000002019.06
pp22-26,321-340. Configuring an image never configures a physical module.
System/IO effects are supplied by their owning runtime, never fabricated here.
"""

import re
from dataclasses import dataclass, field
from .model import fail

DEC = r"(?:0|[1-9][0-9]*)"
WORD = re.compile(r"%(MW|SW|KW)(" + DEC + r")|%(IW|QW|IWS|QWS)(" + DEC + r")\.(" + DEC + r")")
BIT = re.compile(r"(.+):X(" + DEC + r")")
SYSTEM_BIT = re.compile(r"%S([0-9]+)")
# P321-326. Undefined/reserved system objects are deliberately excluded.
SYSTEM_READ = frozenset((0,4,5,6,7,9,10,11,12,13,15,16,17,18,19,20,21,22,23,28,33,38,39,49,50,51,52,59,66,75,90,91,92,93,94,96,101,102,103,104,106,107,109,110,111,112,113,114,115,116,119,124,125,126))
SYSTEM_CLEAR = frozenset((17,18,19,20,28,39))
SYSTEM_WRITE = frozenset((0,9,33,38,49,50,51,59,66,90,91,93,94,101,102,103,104,106,107,109,110,111,112,113,114,115,116,124,125,126))
# Grafcet S21/22/23 are readable here; their write context belongs to G07.
SYSTEM_WORD_READ = frozenset((0,1,6,7,8,11,13,14,15,16,17,18,19,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,62,63,64,65,66,67,70,71,72,75,76,77,78,79,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,166,168,170,171,172,173,174,175,176,177,178,179,180,181,188,189,190,191,192,193,194,195,196,197,198,199,200,201,202,203,204,205,206,210,211,212,213,215,216,217,221,222,223,224,225,226,227,228,229))
SYSTEM_WORD_WRITE = frozenset((0,1,11,17,18,19,33,34,35,36,37,38,49,50,51,52,53,59,60,76,77,78,79,101,102,103,104,105,106,111,112,113,114,121,122,123,148,206,224,225,226,227,228,229))


def native_system_word(text, writable=False):
    """The owning scalar/RTC provider decides eligibility and permissions."""
    from .scalar_numeric import system_word
    from .rtc import reference as rtc_reference

    return bool(system_word(text, writable) or rtc_reference(text, writable))


def word_object(text, writable=False):
    m = WORD.fullmatch(text) if isinstance(text, str) else None
    if m is None:
        fail("unsupported Boolean word object: " + str(text))
    bank = m[1] or m[3]
    index = int(m[2] if m[1] else m[4])
    channel = None if m[1] else int(m[5])
    provider = bank == "SW" and native_system_word(text, writable)
    if bank in ("MW", "SW", "KW"):
        if index >= {"MW":8000, "SW":234, "KW":512}[bank]:
            fail("Boolean word object outside target range: " + text)
        if bank == "SW" and index not in SYSTEM_WORD_READ:
            fail("undefined/reserved system word: " + text)
    else:
        # P22: module 0 addresses cartridges, modules 1..14 the expansion bus.
        # Per-channel eligibility is checked against the actual configuration.
        if index > 14 or (index == 0 and not (100 <= channel <= 199 or 200 <= channel <= 299)) or (index != 0 and channel > 31):
            fail("Boolean IO word outside module/channel address domain: " + text)
    if writable and (bank in ("IW", "IWS", "QWS", "KW") or (bank == "SW" and not provider and index not in SYSTEM_WORD_WRITE)):
        fail("Boolean word object is read-only: " + text)
    return bank, index, channel


def word_bit(text, writable=False):
    m = BIT.fullmatch(text) if isinstance(text, str) else None
    if m is None or int(m[2]) >= 16:
        fail("unsupported word bit address: " + str(text))
    bank, index, channel = word_object(m[1], writable)
    return bank, index, channel, int(m[2])


def system_bit_identity(text):
    """Select one runtime bit identity for native S-decimal aliases only."""
    if not text.startswith("%S"):
        return text
    match = SYSTEM_BIT.fullmatch(text)
    if match is None:
        return text
    return "%S" + (match[1].lstrip("0") or "0")


def system_bit(index, action=None):
    if index not in SYSTEM_READ:
        fail("undefined/reserved or unsupported system bit: %S" + str(index))
    if action is not None:
        if index in SYSTEM_CLEAR and action == "R":
            return
        if index not in SYSTEM_WRITE:
            fail("system bit has no permission for " + action + ": %S" + str(index))


@dataclass
class BooleanConfig:
    input_image_stable: bool = True
    native_expression_edges: bool = False
    word_objects: list = field(default_factory=list)

    def validate(self):
        if type(self.input_image_stable) is not bool or type(self.native_expression_edges) is not bool:
            fail("Boolean context flags must be bool")
        if not isinstance(self.word_objects, list) or any(not isinstance(v, str) for v in self.word_objects) or len(set(self.word_objects)) != len(self.word_objects):
            fail("Boolean word_objects must be a unique address list")
        for text in self.word_objects:
            if word_object(text)[0] not in ("IW", "QW", "IWS", "QWS"):
                fail("Boolean word image declarations are only for IO value/status objects")
        return self

    def to_dict(self):
        self.validate()
        return dict(input_image_stable=self.input_image_stable, native_expression_edges=self.native_expression_edges,
                    word_objects=sorted(self.word_objects))

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, dict) or set(raw) - {"input_image_stable", "native_expression_edges", "word_objects"}:
            fail("unknown/invalid Boolean configuration")
        values = dict(raw)
        return cls(**values).validate()


def config(program):
    value = program.boolean
    if value is None:
        return BooleanConfig()
    if not isinstance(value, BooleanConfig):
        fail("invalid typed Boolean configuration")
    return value.validate()


def validate_operand(program, operand, action=None):
    if ":X" in operand:
        bank, index, _, _ = word_bit(operand, action is not None)
        cfg = config(program)
        base = operand.split(":X",1)[0]
        if bank == "KW" and not hasattr(program, "constants"):
            fail("KW bit access requires the shared Program.constants image from G02")
        if bank in ("IW", "QW", "IWS", "QWS") and base not in cfg.word_objects:
            fail("Boolean IO word needs an explicit configured image identity: " + base)
    elif SYSTEM_BIT.fullmatch(operand):
        system_bit(int(operand[2:]), action)


def uses(program):
    return {m[1] for rung in program.rungs for line in rung for m in re.finditer(r"(%(?:MW|SW|KW)[0-9]+|%(?:IW|QW|IWS|QWS)[0-9]+\.[0-9]+):X[0-9]+",line)}


class BooleanImages:
    """Delegates system/hardware behavior; MW always aliases Machine.words.

    Adapter signature: (action, address, value) -> raw 16-bit word/bool on
    read; any return on write. Called at the exact instruction position.
    Without an adapter, external reads/writes fail explicitly.
    """
    def __init__(self, program, adapter=None):
        self.config = config(program)
        if adapter is not None and not callable(adapter):
            fail("Boolean runtime adapter must be callable")
        self.adapter = adapter

    def external(self, action, address, value=None):
        if self.adapter is None:
            fail("Boolean system/IO runtime adapter required for " + action + " " + address)
        result = self.adapter(action,address,value)
        if action == "read_word" and (type(result) is not int or not 0 <= result <= 65535):
            fail("Boolean runtime word read must return unsigned16")
        if action == "read_bit" and type(result) is not bool:
            fail("Boolean runtime bit read must return bool")
        return result

    def read(self, operand, words, constants=None):
        bank,index,_,bit = word_bit(operand)
        base = operand.split(":X",1)[0]
        if bank == "KW" and constants is None:
            fail("KW bit access requires the shared Machine.constants image from G02")
        value = words[index] if bank == "MW" else constants.get(index, 0) if bank == "KW" else self.external("read_word",base)
        return bool(value & (1 << bit))

    def write(self, operand, value, words):
        bank,index,_,bit = word_bit(operand,True)
        base = operand.split(":X",1)[0]
        # One read-modify-write of the owning word preserves all other bits.
        old = words[index] if bank == "MW" else self.external("read_word",base)
        raw = (old | (1 << bit)) if value else (old & (65535 ^ (1 << bit)))
        if bank == "MW":
            words[index] = raw
        else:
            self.external("write_word",base,raw)
