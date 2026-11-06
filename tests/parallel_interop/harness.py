"""Small runner primitives; missing contracts are PENDING, never skips/passes."""

from dataclasses import dataclass
import hashlib
import importlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DELIVERIES = ROOT / "output/parallel-implementation-2026-11-06/lanes"


class PendingContract(Exception):
    """A real API, primary oracle, or required execution route is not integrated."""


@dataclass(frozen=True)
class Case:
    identity: str
    lane: str
    description: str
    reference: str
    run: object


def equal(actual, expected, context=""):
    if actual != expected:
        raise AssertionError(f"{context}\nexpected={expected!r}\nobserved={actual!r}")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def refused(action, error_types, context=""):
    try:
        action()
    except error_types:
        return
    raise AssertionError("accepted invalid/forged input: " + context)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state(status):
    return [
        status.done,
        status.busy,
        status.aborted,
        status.error,
        status.comm_error,
        status.oper_error,
    ]


class ScriptedTransport:
    """Independent literal PDU source; no peer implementation, sockets, retries."""

    def __init__(self, replies, latency_ms=1):
        self.replies = list(replies)
        self.latency_ms = latency_ms
        self.started = []
        self.cancelled = []
        self.pending = {}

    def start(self, config, pdu, now_ms):
        token = len(self.started)
        self.started.append((config, bytes(pdu), now_ms))
        if token >= len(self.replies):
            raise AssertionError("unexpected extra exchange/retry")
        self.pending[token] = (now_ms + self.latency_ms, self.replies[token])
        return token

    def poll(self, token, now_ms):
        ready, reply = self.pending[token]
        if now_ms < ready or reply is None:
            return None
        del self.pending[token]
        return reply

    def cancel(self, token):
        self.cancelled.append(token)
        self.pending.pop(token, None)


def _artifact(path, work):
    path = Path(path)
    if not path.is_absolute():
        path = work / path
    path = path.resolve()
    require(path.is_file() and path.stat().st_size > 0, f"missing evidence: {path}")
    return {"path": str(path), "sha256": sha256(path)}


def future_cases(include_deferred=False):
    """Adapters receive requests without expected values; the harness owns oracles."""
    from future_corpus import SPECS

    specs = SPECS
    bindings = json.loads((HERE / "bindings.json").read_text())
    result = []
    for spec in specs:
        if spec["lane"] != "G11" and not include_deferred:
            continue
        def run(work, spec=spec):
            lane = spec["lane"]
            if lane != "G11":
                raise PendingContract("DEFERRED_VERSION: outside the current Christmas release scope")
            delivery = DELIVERIES / lane / "DELIVERY.md"
            if not delivery.is_file():
                raise PendingContract(f"{lane}: missing {delivery}")
            binding = bindings.get(lane)
            if not binding:
                raise PendingContract(f"{lane}: real public API adapter not bound")
            if spec.get("oracle_pending"):
                raise PendingContract(spec["oracle_pending"])
            module_name, separator, function_name = binding.partition(":")
            require(separator and function_name, "binding requires module:function")
            module = importlib.import_module(module_name)
            adapter = getattr(module, function_name)
            request = {
                "identity": spec["identity"],
                "lane": lane,
                "scenario": spec["scenario"],
                "required_stages": spec["required_stages"],
            }
            observed = adapter(request, {"root": ROOT, "work": work})
            require(isinstance(observed, dict), "adapter must return an observation object")
            if observed.get("pending"):
                raise PendingContract(str(observed["pending"]))
            equal(observed.get("observed"), spec["expected"], spec["identity"])
            evidence = observed.get("evidence", {})
            bound = {}
            for stage in spec["required_stages"]:
                if stage not in evidence:
                    raise PendingContract(f"{lane}: execution evidence missing for {stage}")
                bound[stage] = _artifact(evidence[stage], work)
            return {"delivery_sha256": sha256(delivery), "evidence": bound}

        result.append(Case(spec["identity"], spec["lane"], spec["description"], spec["reference"], run))
    return result
