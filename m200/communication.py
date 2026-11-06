"""Closed native communication IL forms and typed read-only status objects."""

import re
from .model import fail
from .communication_properties import FIELDS, property_reference

KINDS = {
    "ReadVar": "READ_VAR",
    "WriteVar": "WRITE_VAR",
    "WriteReadVar": "WRITE_READ_VAR",
}
BOOL_FIELDS = {"DONE": "done", "BUSY": "busy", "ABORTED": "aborted", "ERROR": "error"}
NUM_FIELDS = {"COMMERROR": ("i16", "comm_error"), "OPERERROR": ("i32", "oper_error"), **{suffix: ("i16", "property") for suffix in FIELDS}}
ADDRESS = r"%(?:WRITE_READ_VAR|WRITE_VAR|READ_VAR)(?:0|[1-9][0-9]*)"
REFERENCE = ADDRESS + r"\.(?:DONE|BUSY|ABORTED|ERROR|" + "|".join(NUM_FIELDS) + ")"
NUM_REFERENCE = ADDRESS + r"\.(?:" + "|".join(NUM_FIELDS) + ")"


def block_address(value):
    if not isinstance(value, str):
        fail("communication address must be a string")
    m = re.fullmatch(r"%(WRITE_READ_VAR|WRITE_VAR|READ_VAR)(0|[1-9][0-9]*)", value)
    if not m or int(m.group(2)) >= 32:
        fail("invalid native communication address: " + value)
    return m.group(1), int(m.group(2))


def status_reference(value):
    m = re.fullmatch("(" + ADDRESS + r")\.(\w+)", value)
    if not m:
        return None
    key, field = m.groups()
    block_address(key)
    if field in FIELDS:
        property_reference(value)
    if field not in BOOL_FIELDS and field not in NUM_FIELDS:
        fail("unsupported communication status: " + value)
    return key, field


def cpp_name(key):
    kind, index = block_address(key)
    return kind.lower() + "_" + str(index)


def parse_block(rung):
    first = rung[0].split(maxsplit=1)
    if len(first) != 2 or first[0] != "BLK":
        fail("invalid communication block")
    key = first[1]
    block_address(key)
    if len(rung) not in (4, 6) or rung[2] != "EXECUTE" or rung[-1] != "END_BLK":
        fail("unsupported native communication block layout")
    if len(rung) == 6 and rung[4] != "ABORT":
        fail("unsupported communication control pin")

    def pin(line):
        p = line.split(maxsplit=1)
        if len(p) != 2 or p[0] not in ("LD", "LDN"):
            fail("communication pin requires LD/LDN")
        return tuple(p)

    return key, pin(rung[1]), pin(rung[3]) if len(rung) == 6 else ("LD", "0")


def constructor_cpp(key, config):
    kind, native_index = block_address(key)
    cls = {v: k for k, v in KINDS.items()}[kind]
    link = "plc::Link::" + ("Serial1" if config.link == "SL1" else "Ethernet")
    values = [str(native_index), link, str(config.id), str(config.timeout_100ms)]
    if kind == "WRITE_READ_VAR":
        values += list(
            map(
                str,
                [
                    config.first_obj,
                    config.quantity,
                    config.index_data,
                    config.first_read_obj,
                    config.read_quantity,
                    config.index_data_in,
                ],
            )
        )
    else:
        obj = [
            "HoldingWords",
            "DiscreteInputs",
            "Coils",
            "InputWords",
            "SingleCoil",
            "SingleRegister",
        ][config.obj_type]
        values += ["plc::Object::" + obj] + list(
            map(str, [config.first_obj, config.quantity, config.index_data])
        )
    return "plc::" + cls + " " + cpp_name(key) + "{" + ",".join(values) + "};"
