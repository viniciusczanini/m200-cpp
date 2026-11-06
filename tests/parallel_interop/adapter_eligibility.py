"""G20 tests the truthfulness of unresolved eligibility, never protocol support."""

import json
from pathlib import Path
from unittest import mock

from harness import PendingContract, equal, require, refused


SERVICES = ["raw_tcp", "user_udp", "opc_ua", "http_server", "mqtt", "canopen", "profinet", "ethercat", "ethernet_ip_scanner"]


def run_case(request, context):
    try:
        from m200 import network_eligibility as api
    except ImportError as error:
        raise PendingContract("G20 eligibility module is not integrated") from error
    from m200.model import CompileError

    scenario = request["scenario"]
    work = Path(context["work"])
    # Pure catalogue/refusal must not connect, launch processes or write files.
    def forbidden(*args, **kwargs):
        raise AssertionError("eligibility query attempted an external side effect")

    with mock.patch("socket.socket", forbidden), mock.patch("subprocess.Popen", forbidden), mock.patch("pathlib.Path.write_text", forbidden), mock.patch("pathlib.Path.write_bytes", forbidden):
        if scenario["mode"] == "catalogue":
            catalogue = api.catalogue()
            records = {name: api.lookup(name).as_dict() for name in SERVICES}
            states = {}
            for name in SERVICES:
                record = api.lookup(name)
                value = record.state.value if hasattr(record.state, "value") else record.state
                states[name] = value
                require(records[name], "empty eligibility record")
            observations = {"count": len(records), "states": states}
        elif scenario["mode"] == "refusal":
            for name in SERVICES:
                refused(lambda name=name: api.require_native_service(name), (CompileError, ValueError), name)
            for name in ("MQTT", "", "raw-tcp", "unknown_service"):
                refused(lambda name=name: api.lookup(name), (CompileError, ValueError), name)
            refused(lambda: api.catalogue(model="TM200CE40R"), (CompileError, ValueError), "other model")
            observations = {"native_services_refused": 9, "invalid_names_refused": 4, "other_model_refused": True}
            catalogue = api.catalogue()
        else:
            raise PendingContract("G20 unknown eligibility adapter scenario")
    evidence = work / "eligibility-observations.json"
    evidence.write_text(json.dumps({"observed": observations, "catalogue": catalogue}, indent=2, sort_keys=True) + "\n")
    return {"observed": observations, "evidence": {"catalogue": str(evidence)}}
