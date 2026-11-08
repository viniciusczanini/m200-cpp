"""Source-backed TM200CE40T inventory, separate from implementation support.

Research records describe the controller. They do not establish support in this
toolchain, acceptance by Machine Expert Basic, or physical testing.
All implementation stages remain missing until an explicit verified overlay is
added. Source JSON cannot promote its own validation state.
"""

import difflib
import json
from collections import Counter
from pathlib import Path

from .model import fail


TARGET = "TM200CE40T"
STAGES = ("frontend", "il", "reverse", "smbp", "local", "editor", "physical")
_DEFAULT_DIRECTORY = Path(__file__).resolve().parents[1] / "docs" / "capabilities"
_DEFAULT_STATUS = {
    "frontend": "missing",
    "il": "missing",
    "reverse": "missing",
    "smbp": "missing",
    "local": "missing",
    "editor": "pending",
    "physical": "pending",
}


def _read(directory, filename):
    path = directory / filename
    try:
        with path.open(encoding="utf-8") as stream:
            document = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail("cannot load capability inventory " + str(path) + ": " + str(error))
    if not isinstance(document, dict):
        fail("invalid capability inventory object: " + str(path))
    if (
        not isinstance(document.get("capabilities"), list)
        or not document["capabilities"]
    ):
        fail("empty or invalid capabilities in " + str(path))
    return document


def _sources(document, domain):
    raw = document.get("sources")
    if domain == "instruction":
        if not isinstance(raw, dict):
            fail("invalid instruction source catalogue")
        items = raw.items()
    else:
        if not isinstance(raw, list) or not all(isinstance(x, dict) for x in raw):
            fail("invalid hardware source catalogue")
        items = ((entry.get("id"), entry) for entry in raw)
    result = {}
    for source_id, record in items:
        if (
            not isinstance(source_id, str)
            or not source_id
            or not isinstance(record, dict)
        ):
            fail("invalid capability source in " + domain)
        identifier = domain + "." + source_id
        if identifier in result:
            fail("duplicate capability source: " + identifier)
        if not (record.get("document") or record.get("document_reference")):
            fail("capability source missing document reference: " + identifier)
        result[identifier] = dict(record)
    if not result:
        fail("missing capability sources in " + domain)
    return result


def catalogue(*, directory=None, model=TARGET):
    """Load both audited inventories with conservative independent stage status.

    ``directory`` supports reading an inspectable copied catalogue. Invalid data,
    unknown evidence references, duplicate IDs and other models fail closed.
    Returned objects are fresh for each call; callers cannot mutate future state.
    """
    if model != TARGET:
        fail("capability model is unsupported: " + str(model) + "; expected " + TARGET)
    directory = _DEFAULT_DIRECTORY if directory is None else Path(directory)
    instructions = _read(directory, "instructions.json")
    hardware = _read(directory, "hardware.json")
    if instructions.get("target") != model:
        fail("instruction capability model does not match " + model)
    resources = instructions.get("target_object_budgets")
    if not isinstance(resources, dict) or not resources:
        fail("missing target resource limits in instruction inventory")
    sources = {}
    records = []
    identifiers = set()
    for domain, document in (("instruction", instructions), ("hardware", hardware)):
        sources.update(_sources(document, domain))
        for raw in document["capabilities"]:
            if (
                not isinstance(raw, dict)
                or not isinstance(raw.get("id"), str)
                or not raw["id"]
            ):
                fail("invalid capability ID in " + domain)
            identifier = raw["id"]
            if identifier in identifiers:
                fail("duplicate capability ID: " + identifier)
            identifiers.add(identifier)
            if raw.get("model", model) != model:
                fail("capability model mismatch: " + identifier)
            refs = (
                raw.get("sources") if domain == "instruction" else raw.get("evidence")
            )
            if not isinstance(refs, list) or not refs:
                fail("capability missing source evidence: " + identifier)
            evidence = []
            for ref in refs:
                if not isinstance(ref, dict) or not isinstance(ref.get("source"), str):
                    fail("invalid source evidence: " + identifier)
                source_id = domain + "." + ref["source"]
                if source_id not in sources or not ref.get("pages"):
                    fail(
                        "unknown source or missing pages for "
                        + identifier
                        + ": "
                        + source_id
                    )
                evidence.append(dict(ref, source=source_id))
            records.append(
                dict(
                    raw,
                    domain=domain,
                    model=model,
                    evidence=evidence,
                    status=dict(_DEFAULT_STATUS),
                )
            )
    return {
        "target": model,
        "sources": sources,
        "resources": resources,
        "tasks": instructions.get("tasks", {}),
        "capabilities": records,
        "unknowns": {
            "instruction": instructions.get("genuine_unknowns", []),
            "hardware": hardware.get("unknowns", []),
        },
        "conflicts": hardware.get("conflicts", []),
        "validation_boundaries": [
            "Inventory is documentary evidence, not toolchain support.",
            "Editor acceptance and physical validation are pending.",
            *hardware.get("validation_boundaries", []),
        ],
    }


def lookup(identifier, *, directory=None, model=TARGET):
    """Return a documented record or an actionable M200-E diagnostic."""
    data = catalogue(directory=directory, model=model)
    for record in data["capabilities"]:
        if record["id"] == identifier:
            return record
    choices = [record["id"] for record in data["capabilities"]]
    matches = difflib.get_close_matches(str(identifier), choices, n=3)
    hint = (
        "; nearby IDs: " + ", ".join(matches)
        if matches
        else "; use catalogue() to inspect known IDs"
    )
    fail("unknown capability " + repr(identifier) + " for " + model + hint)


def summary(*, directory=None, model=TARGET):
    """Count each stage separately without treating inventory as completion."""
    data = catalogue(directory=directory, model=model)
    records = data["capabilities"]
    counts = {
        stage: dict(Counter(record["status"][stage] for record in records))
        for stage in STAGES
    }
    return {
        "target": model,
        "total": len(records),
        "domains": dict(Counter(record["domain"] for record in records)),
        "stages": counts,
        "complete": all(
            all(record["status"][stage] == "implemented" for stage in STAGES)
            for record in records
        ),
        "pending_external_validation": any(
            record["status"][stage] != "implemented"
            for record in records
            for stage in ("editor", "physical")
        ),
        "validation_boundaries": data["validation_boundaries"],
    }
