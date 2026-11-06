"""SR provenance only. Executable bodies always come from native InstructionLines."""

import json

from .jsonio import loads
from .model import fail

ORIGIN_MARKER = "\nM200_CPP_SR_ORIGINS="
ORIGIN_LIMIT = 65536


def origin_comment(origins):
    payload = json.dumps(origins, separators=(",", ":"), ensure_ascii=True)
    if len(payload.encode("utf-8")) > ORIGIN_LIMIT:
        fail("SR source origin payload exceeds 64 KiB")
    return ORIGIN_MARKER + payload


def import_origins(node, fallback):
    comment = node.findtext("MainComment", "")
    if ORIGIN_MARKER not in comment:
        return [fallback]
    if comment.count(ORIGIN_MARKER) != 1:
        fail("ambiguous SR source origin payload")
    payload = comment.split(ORIGIN_MARKER, 1)[1]
    if len(payload.encode("utf-8")) > ORIGIN_LIMIT:
        fail("SR source origin payload exceeds 64 KiB")
    origins = loads(payload)
    if not isinstance(origins, list) or len(origins) != 1:
        fail("invalid SR source origin mapping")
    # Field/type/source-location checks belong to the IL context validator.
    return origins
