"""Independent finite SDK PDU/state vectors; no network or physical peer.

Requests contain stimuli only. Expected PDUs/data/statuses stay in this module.
Protocol basis: Modbus Application Protocol V1.1b3 sections6.1–6.6,6.11–6.12,
6.17; admitted error/edge policy in the G11 native-async contract.
"""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from parallel_semantics.g11_sdk_host import SDKExecutionError, run_sequence

ROOT = Path(__file__).resolve().parents[1]
IDLE = dict(done=False, busy=False, aborted=False, error=False, comm_error=0, oper_error=0)
BUSY = dict(done=False, busy=True, aborted=False, error=False, comm_error=0, oper_error=0)
DONE = dict(done=True, busy=False, aborted=False, error=False, comm_error=0, oper_error=0)
ABORTED = dict(done=False, busy=False, aborted=True, error=False, comm_error=2, oper_error=0)


def error(comm, oper):
    return dict(done=False, busy=False, aborted=False, error=True, comm_error=comm, oper_error=oper)


def call(block="block", execute=False, abort=False):
    return {"block": block, "execute": execute, "abort": abort}


def exchange(config, initial, response):
    return {"blocks": {"block": config}, "initial_words": initial, "events": [
        {"calls": [call()]}, {"calls": [call(execute=True)]},
        {"calls": [call(execute=True)], "poll": {"kind": "response", "hex": response}},
    ]}


def read(**changes):
    return dict(kind="READ_VAR", link="SL1", id=1, timeout_100ms=100,
                obj_type=0, first_obj=0, quantity=2, index_data=100, **changes)


WIRE = [
    ("FC1", dict(kind="READ_VAR", obj_type=2, first_obj=19, quantity=10, index_data=100),
     {"99": 777, "100": 999, "101": 888}, "01025501", "010013000A", {"99": 777, "100": 341, "101": 888}),
    ("FC2", dict(kind="READ_VAR", obj_type=1, first_obj=32, quantity=9, index_data=100),
     {"100": 999, "101": 888}, "0202AA01", "0200200009", {"100": 426, "101": 888}),
    ("FC3", dict(kind="READ_VAR", obj_type=0, first_obj=107, quantity=3, index_data=100),
     {"99": 777, "100": 1111, "101": 2222, "102": 3333, "103": 888},
     "03068000FFFF1234", "03006B0003", {"99": 777, "100": 32768, "101": 65535, "102": 4660, "103": 888}),
    ("FC4", dict(kind="READ_VAR", link="ETH1", obj_type=3, first_obj=1, quantity=2, index_data=100),
     {"100": 1111, "101": 2222}, "0404000100FF", "0400010002", {"100": 1, "101": 255}),
    ("FC5", dict(kind="WRITE_VAR", obj_type=4, first_obj=172, quantity=1, index_data=100),
     {"100": 1}, "0500ACFF00", "0500ACFF00", {"100": 1}),
    ("FC6", dict(kind="WRITE_VAR", obj_type=5, first_obj=1, quantity=1, index_data=100),
     {"100": 42330}, "060001A55A", "060001A55A", {"100": 42330}),
    ("FC15", dict(kind="WRITE_VAR", obj_type=2, first_obj=19, quantity=10, index_data=100),
     {"100": 341}, "0F0013000A", "0F0013000A025501", {"100": 341}),
    ("FC16", dict(kind="WRITE_VAR", obj_type=0, first_obj=1, quantity=2, index_data=100),
     {"100": 4660, "101": 43981}, "1000010002", "1000010002041234ABCD", {"100": 4660, "101": 43981}),
    ("FC23", dict(kind="WRITE_READ_VAR", first_obj=32, quantity=2, index_data=100,
                  first_read_obj=16, read_quantity=3, index_data_in=200),
     {"100": 10, "101": 48879, "199": 777, "200": 1111, "201": 2222, "202": 3333, "203": 888},
     "1706000100028000", "17001000030020000204000ABEEF",
     {"100": 10, "101": 48879, "199": 777, "200": 1, "201": 2, "202": 32768, "203": 888}),
]


class NativeModbusAsync(unittest.TestCase):
    def setUp(self):
        self.sequence = 0

    def observe(self, request):
        self.sequence += 1
        archive = os.environ.get("M200_G11_TEST_OUTPUT")
        if archive:
            folder = Path(archive) / (self._testMethodName + "-%02d" % self.sequence)
            folder.mkdir(parents=True, exist_ok=False)
            (folder / "request.json").write_text(json.dumps(request, indent=2) + "\n")
            result = run_sequence(request=copy.deepcopy(request), repo=ROOT, work=folder)
            (folder / "actual.json").write_text(json.dumps(result, indent=2) + "\n")
            return result
        with tempfile.TemporaryDirectory() as d:
            return run_sequence(request=copy.deepcopy(request), repo=ROOT, work=Path(d))

    def check(self, actual, expected):
        # Subset selection observes declared fields only; no outcome is inferred
        # from another engine or recomputed from the request by the test adapter.
        for key, wanted in expected.items():
            self.assertIn(key, actual)
            self.assertEqual(actual[key], wanted, key)

    def test_all_nine_documented_functions_encode_decode_literal_PDUs(self):
        for name, config, initial, response, pdu, words in WIRE:
            with self.subTest(function=name):
                self.check(self.observe(exchange(config, initial, response)),
                    {"request_hexes": [pdu], "statuses": {"block": DONE}, "words": words, "cancel_count": 0})

    def test_outgoing_snapshot_busy_reconfiguration_and_captured_transport(self):
        outgoing = exchange(dict(kind="WRITE_VAR", first_obj=1, quantity=2, index_data=100),
            {"100": 4660, "101": 43981}, "1000010002")
        outgoing["events"][2]["write_words"] = {"100": 1, "101": 2}
        outgoing["events"][2]["set_properties"] = [["block", "FirstObj", 9], ["block", "Id", 2]]
        self.check(self.observe(outgoing), {"request_hexes": ["1000010002041234ABCD"],
            "request_ids": [1], "statuses": {"block": DONE}, "words": {"100": 1, "101": 2}})
        reconfigure = exchange(read(), {"100": 1111, "101": 2222, "200": 3333}, "0304000B0016")
        reconfigure["events"][2]["set_properties"] = [["block", "IndexData", 200], ["block", "FirstObj", 32], ["block", "Quantity", 1], ["block", "Id", 2]]
        reconfigure["events"] += [{"calls": [call()]}, {"calls": [call(execute=True)]},
            {"calls": [call(execute=True)], "poll": {"kind": "response", "hex": "03020021"}}]
        self.check(self.observe(reconfigure), {"request_hexes": ["0300000002", "0300200001"],
            "request_ids": [1, 2], "configured_index_data": {"block": 200},
            "statuses": {"block": DONE}, "words": {"100": 11, "101": 22, "200": 33}})
        rebound = exchange(read(), {"100": 1111, "101": 2222}, "0304000B0016")
        rebound["events"][2]["rebind_transport"] = True
        self.check(self.observe(rebound), {"request_hexes": ["0300000002"], "statuses": {"block": DONE},
            "words": {"100": 11, "101": 22}, "cancel_count": 0})

    def test_malformed_responses_are_atomic_for_all_decode_shapes(self):
        bad = [
            (read(), {"100": 1111, "101": 2222}, "0404000B0016"),
            (read(), {"100": 1111, "101": 2222}, "0302000B"),
            (read(), {"100": 1111, "101": 2222}, "0304000B"),
            (read(), {"100": 1111, "101": 2222}, "0304000B0016AA"),
            (dict(kind="READ_VAR", obj_type=2, quantity=9, index_data=100), {"100": 1111}, "01020102"),
            (dict(kind="WRITE_VAR", obj_type=4, first_obj=172, quantity=1, index_data=100), {"100": 1}, "0500AC0000"),
            (dict(kind="WRITE_VAR", obj_type=5, first_obj=1, quantity=1, index_data=100), {"100": 42330}, "060002A55A"),
            (dict(kind="WRITE_VAR", obj_type=2, first_obj=19, quantity=10, index_data=100), {"100": 341}, "0F00130009"),
            (dict(kind="WRITE_VAR", first_obj=1, quantity=2, index_data=100), {"100": 4660, "101": 43981}, "1000020002"),
            (dict(kind="WRITE_READ_VAR", first_obj=32, quantity=1, index_data=100, first_read_obj=16, read_quantity=3, index_data_in=200),
             {"100": 10, "200": 1111, "201": 2222, "202": 3333}, "170400010002"),
            (read(), {"100": 1111, "101": 2222}, "830200"),
        ]
        for config, initial, response in bad:
            with self.subTest(response=response):
                self.check(self.observe(exchange(config, initial, response)),
                    {"statuses": {"block": error(0, 2)}, "words": initial, "cancel_count": 1})
        oversized = exchange(read(), {"100": 1111, "101": 2222}, "0304000B0016")
        oversized["events"][2]["poll"]["size"] = 254
        self.check(self.observe(oversized), {"statuses": {"block": error(0, 2)},
            "words": {"100": 1111, "101": 2222}, "cancel_count": 1})

    def test_timeout_channel_ownership_and_abort_release(self):
        timeout = exchange({**read(), "timeout_100ms": 1}, {"100": 1111, "101": 2222}, "0304000B0016")
        timeout["events"][2] = {"now_ms": 1000, "calls": [call(execute=True)]}
        timeout["events"].append({"now_ms": 1010, "calls": [call(execute=True)], "poll": {"kind": "response", "hex": "0304000B0016"}})
        self.check(self.observe(timeout), {"statuses": {"block": error(1, 0)}, "words": {"100": 1111, "101": 2222}, "cancel_count": 1})
        forever = copy.deepcopy(timeout)
        forever["blocks"]["block"]["timeout_100ms"] = 0
        forever["events"][2]["now_ms"] = 100000
        forever["events"][3]["now_ms"] = 100010
        self.check(self.observe(forever), {"statuses": {"block": DONE}, "words": {"100": 11, "101": 22}, "cancel_count": 0})
        channel = {"blocks": {"first": {**read(), "quantity": 1}, "second": {**read(), "id": 2, "first_obj": 1, "quantity": 1, "index_data": 200}},
            "initial_words": {"100": 1111, "200": 2222}, "events": [
                {"calls": [call("first"), call("second")]},
                {"calls": [call("first", True), call("second", True)], "capture": ["first", "second"]},
                {"calls": [call("first", True, True), call("second")]},
                {"calls": [call("second", True)]},
                {"calls": [call("second", True)], "poll": {"kind": "response", "hex": "03020021"}},
            ]}
        self.check(self.observe(channel), {"request_hexes": ["0300000001", "0300010001"],
            "snapshots": [{"block": "first", **BUSY}, {"block": "second", **error(255, 11)}],
            "statuses": {"first": ABORTED, "second": DONE}, "words": {"100": 1111, "200": 33}, "cancel_count": 1})
        links = copy.deepcopy(channel)
        links["blocks"]["second"]["link"] = "ETH1"
        links["events"] = links["events"][:2] + [{"calls": [call("first", True, True), call("second", True, True)]}]
        self.check(self.observe(links), {"request_hexes": ["0300000001", "0300010001"], "request_links": [1, 2],
            "snapshots": [{"block": "first", **BUSY}, {"block": "second", **BUSY}],
            "statuses": {"first": ABORTED, "second": ABORTED}, "cancel_count": 2})

    def test_error_mapping_initial_edges_and_missing_transport(self):
        exception = exchange(read(), {"100": 1111, "101": 2222}, "8302")
        self.check(self.observe(exception), {"statuses": {"block": error(254, 2)}, "words": {"100": 1111, "101": 2222}})
        transport_error = exchange(read(), {"100": 1111, "101": 2222}, "")
        transport_error["events"][2]["poll"] = {"kind": "error", "comm_error": 255, "oper_error": 6}
        self.check(self.observe(transport_error), {"statuses": {"block": error(255, 6)}, "words": {"100": 1111, "101": 2222}})
        rejected = exchange(read(), {"100": 1111, "101": 2222}, "")
        rejected["events"] = rejected["events"][:2]
        rejected["events"][1]["start_error"] = [255, 6]
        self.check(self.observe(rejected), {"statuses": {"block": error(255, 6)}, "cancel_count": 0})
        broadcast = exchange(dict(kind="WRITE_VAR", id=0, obj_type=5, first_obj=7, quantity=1, index_data=100), {"100": 42}, "")
        broadcast["events"][2]["poll"] = {"kind": "broadcast"}
        self.check(self.observe(broadcast), {"request_hexes": ["060007002A"], "statuses": {"block": DONE}, "words": {"100": 42}})
        reply_to_broadcast = copy.deepcopy(broadcast)
        reply_to_broadcast["events"][2]["poll"] = {"kind": "response", "hex": "060007002A"}
        self.check(self.observe(reply_to_broadcast), {"statuses": {"block": error(0, 2)}, "words": {"100": 42}})
        unicast_ack = exchange(read(), {"100": 1111, "101": 2222}, "")
        unicast_ack["events"][2]["poll"] = {"kind": "broadcast"}
        self.check(self.observe(unicast_ack), {"statuses": {"block": error(0, 2)}, "words": {"100": 1111, "101": 2222}})
        for mode in ("none", "partial"):
            absent = {"blocks": {"block": read()}, "transport": mode, "events": [{"calls": [call()]}, {"calls": [call(execute=True)]}]}
            self.check(self.observe(absent), {"request_hexes": [], "statuses": {"block": error(255, 15)}})
        first_true = {"blocks": {"block": read()}, "events": [{"calls": [call(execute=True)]}, {"calls": [call(execute=True)]}]}
        self.check(self.observe(first_true), {"request_hexes": [], "statuses": {"block": IDLE}})
        invalid = {"blocks": {"block": read()}, "events": [{"calls": [call()]},
            {"set_properties": [["block", "Quantity", 0]], "calls": [call(execute=True)]}]}
        self.check(self.observe(invalid), {"request_hexes": [], "statuses": {"block": error(6, 0)}})

    def test_receive_word_barrier_preserves_flags_and_atomic_poison_state(self):
        flags = {"S18": True, "S17": True, "SW17": 4}
        initial = {"99": 777, "100": 1111, "101": 2222, "102": 888}
        valid = exchange(read(), initial, "0304000B0016")
        valid.update(poison_words={"99": 128, "100": 65535, "101": 1, "102": 32768}, sticky_flags=True, probe_known_words=[100, 101])
        self.check(self.observe(valid), {"words": {"99": 777, "100": 11, "101": 22, "102": 888},
            "poison": {"99": 128, "100": 0, "101": 0, "102": 32768}, "flags": flags,
            "known_words": {"100": 11, "101": 22}, "statuses": {"block": DONE}})
        fc23 = exchange(dict(kind="WRITE_READ_VAR", first_obj=32, quantity=1, index_data=10,
            first_read_obj=16, read_quantity=2, index_data_in=100), {"10": 4660, **initial}, "1704000B0016")
        fc23.update(poison_words=copy.deepcopy(valid["poison_words"]), sticky_flags=True, probe_known_words=[100, 101])
        self.check(self.observe(fc23), {"request_hexes": ["170010000200200001021234"],
            "words": {"10": 4660, "99": 777, "100": 11, "101": 22, "102": 888},
            "poison": {"10": 0, "99": 128, "100": 0, "101": 0, "102": 32768}, "flags": flags})
        malformed = copy.deepcopy(valid)
        malformed.pop("probe_known_words")
        malformed["events"][2]["poll"]["hex"] = "0304000B"
        self.check(self.observe(malformed), {"words": initial, "poison": valid["poison_words"], "flags": flags, "statuses": {"block": error(0, 2)}})
        aborted = copy.deepcopy(malformed)
        aborted["events"][2] = {"calls": [call(execute=True, abort=True)]}
        aborted["events"].append({"calls": [call(execute=True, abort=True)], "poll": {"kind": "response", "hex": "0304000B0016"}})
        self.check(self.observe(aborted), {"words": initial, "poison": valid["poison_words"], "flags": flags, "statuses": {"block": ABORTED}, "cancel_count": 1})
        outgoing = exchange(dict(kind="WRITE_VAR", obj_type=5, quantity=1, index_data=100), {"100": 4660}, "0600001234")
        outgoing["poison_words"] = {"100": 65535}
        with self.assertRaises(SDKExecutionError) as caught:
            self.observe(outgoing)
        self.assertNotEqual(caught.exception.returncode, 0)
        self.assertNotIn("RAW_START", caught.exception.stderr)


if __name__ == "__main__":
    unittest.main()
