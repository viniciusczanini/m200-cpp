"""Native label identity; labels live in the actual IL, never source metadata."""

import re

from .model import fail

JUMPS = ("JMP", "JMPC", "JMPCN")


def label_name(value):
    match = re.fullmatch(r"%L(0|[1-9][0-9]*)", value)
    if match is None or int(match[1]) >= 64:
        fail("label outside native %L0..%L63: " + value)
    return value


def split_label(rung):
    if rung and rung[0].startswith("%L"):
        if not rung[0].endswith(":"):
            fail("label declaration must end with a colon")
        return label_name(rung[0][:-1]), rung[1:]
    return None, rung


def destinations(program):
    labels = {}
    for index, rung in enumerate(program.rungs):
        label, _ = split_label(rung)
        if label is not None:
            if label in labels:
                fail("duplicate label: " + label)
            labels[label] = index
    return labels
