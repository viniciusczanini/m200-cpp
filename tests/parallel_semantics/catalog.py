"""Finite case inventory with explicit priority and deferred-version dispositions."""

import json
from pathlib import Path

from .source_cases import all_source_cases
from .g09_cases import CASES as G09_FROZEN_CASES
from .contract_cases import CASES as CONTRACT_CASES
from .priority_cases import CASES as PRIORITY_CASES, PENDING_CASES
from .combined_cases import CASES as COMBINED_CASES, TAINT_CASE, CONSTANT_BOUNDS, FLAG_CLEAR_CASE, OWNERSHIP_REPRO, INDEX_TAINT_CASE, full_constant_case
from .g07_frozen_cases import CASES as G07_SOURCE_CASES, HOST_CASES as G07_HOST_CASES, BOUND_CASE, stress_cases as g07_stress_cases


HERE = Path(__file__).resolve().parent


def configuration():
    return json.loads((HERE/"scope.json").read_text()), json.loads((HERE/"adapters.json").read_text())


def disposition(case, scope):
    if case.name in scope["deferred_cases"] or any(case.name.startswith(p) for p in scope["deferred_prefixes"]):
        return "DEFERRED_VERSION"
    if not set(case.groups).intersection(scope["active_groups"]):
        return "DEFERRED_VERSION"
    return "PREPARED_NOT_EXECUTED"


def inventory():
    scope, registry = configuration()
    cases = all_source_cases()+CONTRACT_CASES+PRIORITY_CASES+PENDING_CASES
    cases += G07_SOURCE_CASES+G07_HOST_CASES+[BOUND_CASE]+g07_stress_cases()
    cases += COMBINED_CASES+[TAINT_CASE,CONSTANT_BOUNDS,FLAG_CLEAR_CASE,OWNERSHIP_REPRO,INDEX_TAINT_CASE,full_constant_case()]
    cases += G09_FROZEN_CASES
    if len({case.name for case in cases}) != len(cases):
        raise ValueError("Duplicate independent semantic case identity")
    bindings = {item["key"]:item for item in registry["bindings"]}
    result = []
    for case in cases:
        if case.adapter not in bindings:
            raise ValueError("Case has no explicit adapter manifest entry: "+case.name)
        result.append((case,disposition(case,scope),bindings[case.adapter]))
    return result
