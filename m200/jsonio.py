"""Bounded, duplicate-rejecting JSON at file input boundaries."""

import json
from .model import fail


def loads(text):
    if len(text.encode("utf-8")) > 20_000_000:
        fail("JSON exceeds 20 MB input limit")

    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                fail("duplicate JSON key: " + key)
            out[key] = value
        return out

    try:
        data = json.loads(text, object_pairs_hook=pairs)
    except RecursionError:
        fail("JSON depth exceeds parser limit")
    except (ValueError, OverflowError) as exc:
        fail("invalid JSON: " + str(exc))
    pending = [(data, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            fail("JSON depth exceeds 64")
        values = (
            item.values()
            if isinstance(item, dict)
            else item
            if isinstance(item, list)
            else ()
        )
        pending.extend((v, depth + 1) for v in values)
    return data
