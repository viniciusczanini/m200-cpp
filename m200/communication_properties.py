"""Native communication word properties (GEN 176,181,186).

Property words carry unsigned bit patterns in the SDK's signed i16 type. Link
uses the *native* codes, not the historical SDK constructor Link enum.
"""
import re
from .model import fail

# Enum ordinal, native suffix, config attribute, native link special case.
PROPERTIES = (
    ("Link", "LINK", "link"),
    ("Id", "ID", "id"),
    ("Timeout", "TIMEOUT", "timeout_100ms"),
    ("ObjType", "OBJTYPE", "obj_type"),
    ("FirstObj", "FIRSTOBJ", "first_obj"),
    ("Quantity", "QUANTITY", "quantity"),
    ("IndexData", "INDEXDATA", "index_data"),
    ("FirstWriteObj", "FIRSTWRITEOBJ", "first_obj"),
    ("WriteQuantity", "WRITEQUANTITY", "quantity"),
    ("IndexDataOut", "INDEXDATAOUT", "index_data"),
    ("FirstReadObj", "FIRSTREADOBJ", "first_read_obj"),
    ("ReadQuantity", "READQUANTITY", "read_quantity"),
    ("IndexDataIn", "INDEXDATAIN", "index_data_in"),
)
FIELDS = {suffix: attr for _, suffix, attr in PROPERTIES}
ENUMS = {suffix: name for name, suffix, _ in PROPERTIES}
NATIVE_LINKS = {1: "SL1", 2: "SL2", 3: "ETH1", 4: "SL3"}
_COMMON = {"LINK", "TIMEOUT"}
DOMAINS = {
    "READ_VAR": _COMMON | {"ID", "OBJTYPE", "FIRSTOBJ", "QUANTITY", "INDEXDATA"},
    "WRITE_VAR": _COMMON | {"ID", "OBJTYPE", "FIRSTOBJ", "QUANTITY", "INDEXDATA"},
    "WRITE_READ_VAR": _COMMON | {"ID", "OBJTYPE", "FIRSTWRITEOBJ", "WRITEQUANTITY", "INDEXDATAOUT", "FIRSTREADOBJ", "READQUANTITY", "INDEXDATAIN"},
}
BUFFER_FIELDS = {"INDEXDATA", "INDEXDATAOUT", "INDEXDATAIN"}
BUFFER_PROPERTIES = BUFFER_FIELDS | {"QUANTITY", "WRITEQUANTITY", "READQUANTITY", "OBJTYPE"}


def property_field(kind, ordinal):
    if type(ordinal) is not int or not 0 <= ordinal < len(PROPERTIES):
        fail("invalid CommProperty enum")
    suffix = PROPERTIES[ordinal][1]
    if suffix not in DOMAINS.get(kind, ()):
        fail("communication property does not belong to " + kind + ": " + suffix)
    return suffix


def property_reference(text, writable=False):
    m = re.fullmatch(r"(%(WRITE_READ_VAR|WRITE_VAR|READ_VAR)(0|[1-9][0-9]*))\.([A-Z]+)", text)
    if not m or m[4] not in FIELDS:
        return None
    maximum = 32
    if int(m[3]) >= maximum or m[4] not in DOMAINS[m[2]]:
        fail("invalid native communication property: " + text)
    return m[1], m[4]


def initial_properties(config):
    return {
        suffix: (next(n for n, link in NATIVE_LINKS.items() if link == config.link)
                 if suffix == "LINK" else getattr(config, FIELDS[suffix]))
        for suffix in DOMAINS[config.kind]
    }


def effective_config(base, properties):
    """Validate the complete snapshot at Execute, never during individual writes."""
    values = base.to_dict()
    for suffix in DOMAINS[base.kind]:
        value = properties[suffix]
        if suffix == "LINK":
            if value not in NATIVE_LINKS:
                fail("invalid dynamic communication LINK")
            value = NATIVE_LINKS[value]
        values[FIELDS[suffix]] = value
    return type(base).from_dict(values)


def signed_word(value):
    value &= 65535
    return value - 65536 if value & 32768 else value


def has_buffer_writes(program):
    """Actual native IL effects, independent of source/origin metadata."""
    from .numeric import is_operation, instruction_operation
    rungs = list(program.rungs) + [r for definition in program.subroutines.values() for r in definition.rungs]
    for rung in rungs:
        for line in rung:
            if is_operation(line):
                target, _, _ = instruction_operation(line)
                prop = property_reference(target, True)
                if prop and prop[1] in BUFFER_PROPERTIES:
                    return True
    return False
