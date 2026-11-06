"""Literal protocol and local-engine interop oracles, independent of the peer."""

from dataclasses import replace

from harness import Case, ScriptedTransport, equal, require, refused, state


PROTOCOL = "Modbus Application Protocol V1.1b3, sections 4/6; docs/capabilities/MODBUS-PARITY-AUDIT.md"
FB = "EIO0000003289.04 pp171-192,204-205; local engine policies explicitly identified"
IDLE = [False, False, False, False, 0, 0]
BUSY = [False, True, False, False, 0, 0]
DONE = [True, False, False, False, 0, 0]


def _wire_case(identity, config_values, words, expected_hex):
    def run(work):
        from m200.modbus import ModbusConfig, encode_request

        values = [0] * 8000
        for index, value in words.items():
            values[index] = value
        before = values.copy()
        encoded = encode_request(ModbusConfig(**config_values), values)
        equal(encoded, bytes.fromhex(expected_hex), identity)
        equal(values, before, "encoding cannot mutate the shared word image")
        return {"request_hex": encoded.hex(), "oracle": expected_hex}

    return Case(identity, "G11", "literal request bytes and shared-buffer immutability", PROTOCOL, run)


def _quantity_case(identity, good, bad):
    def run(work):
        from m200.modbus import ModbusConfig

        config = ModbusConfig(**good)
        equal(config.to_dict()["kind"], good["kind"])
        for invalid in bad:
            refused(lambda invalid=invalid: ModbusConfig(**{**good, **invalid}), ValueError, str(invalid))
        return {"accepted_boundary": good, "refused_outside": bad}

    return Case(identity, "G11", "last valid quantity/span and immediately invalid neighbors", FB, run)


def _responses(work):
    from m200.modbus import ModbusConfig, decode_response, ModbusProtocolError, ModbusExceptionResponse

    config = ModbusConfig(kind="READ_VAR", quantity=2)
    request = bytes.fromhex("03 0000 0002")
    equal(list(decode_response(config, request, bytes.fromhex("03 04 1234 ffff"))), [4660, 65535])
    invalid = ["", "04 04 1234 ffff", "03 02 1234", "03 04 1234", "03 04 1234 ffff 00", "83 00", "83 02 00"]
    for response in invalid:
        refused(lambda response=response: decode_response(config, request, bytes.fromhex(response)), ModbusProtocolError, response)
    try:
        decode_response(config, request, bytes.fromhex("83 02"))
    except ModbusExceptionResponse as error:
        equal([error.comm_error, error.oper_error], [254, 2])
    else:
        raise AssertionError("exception response was presented as success")
    bits = ModbusConfig(kind="READ_VAR", obj_type=2, quantity=9)
    equal(list(decode_response(bits, bytes.fromhex("01 0000 0009"), bytes.fromhex("01 02 01 01"))), [257])
    refused(lambda: decode_response(bits, bytes.fromhex("01 0000 0009"), bytes.fromhex("01 02 01 02")), ModbusProtocolError, "nonzero unused padding")
    return {"valid_words": [4660, 65535], "valid_bits": [257], "refused_response_hex": invalid}


def _tcp_identity(work):
    from m200.modbus import encode_tcp, decode_tcp, ModbusProtocolError

    pdu = bytes.fromhex("03 04 abcd 8000")
    expected = bytes.fromhex("1234 0000 0007 01 03 04 abcd 8000")
    equal(encode_tcp(0x1234, 1, pdu), expected)
    equal(decode_tcp(expected, transaction_id=0x1234, unit_id=1), pdu)
    invalid = [
        bytes.fromhex("1234 0001 0007 01 03 04 abcd 8000"),
        bytes.fromhex("4321 0000 0007 01 03 04 abcd 8000"),
        bytes.fromhex("1234 0000 0007 02 03 04 abcd 8000"),
        bytes.fromhex("1234 0000 0008 01 03 04 abcd 8000"),
        expected + b"\0",
    ]
    for frame in invalid:
        refused(lambda frame=frame: decode_tcp(frame, transaction_id=0x1234, unit_id=1), ModbusProtocolError, frame.hex())
    return {"adu_hex": expected.hex(), "rejected_identity_or_framing_mutants": len(invalid)}


def _engine_initial_held(work):
    from m200.modbus import ModbusConfig, CommunicationEngine

    transport = ScriptedTransport([bytes.fromhex("03 02 1234")])
    engine, config, words = CommunicationEngine(transport), ModbusConfig(index_data=7999), [7] * 8000
    levels = [True, True, False, True, True, True, False]
    rows = [state(engine.update("%READ_VAR0", config, level, False, now, words)) for now, level in enumerate(levels)]
    equal(rows, [IDLE, IDLE, IDLE, BUSY, DONE, DONE, IDLE])
    equal(words[7999], 4660)
    equal(words[:7999], [7] * 7999)
    equal(len(transport.started), 1, "held Execute must not schedule a retry")
    return {"levels": levels, "literal_status_rows": rows}


def _engine_dynamic_snapshot(work):
    from m200.modbus import ModbusConfig, CommunicationEngine

    original = ModbusConfig(index_data=7998, quantity=2)
    changed = replace(original, index_data=0, quantity=1, first_obj=3)
    transport = ScriptedTransport([bytes.fromhex("03 04 1234 ffff"), bytes.fromhex("03 02 0007")], latency_ms=2)
    engine = CommunicationEngine(transport)
    bank_a, bank_b = [17] * 8000, [23] * 8000
    equal(state(engine.update("r", original, False, False, 0, bank_a)), IDLE)
    equal(state(engine.update("r", original, True, False, 1, bank_a)), BUSY)
    equal(state(engine.update("r", changed, False, False, 2, bank_b)), BUSY)
    equal(state(engine.update("r", changed, True, False, 3, bank_b)), DONE)
    equal(bank_a, [17] * 7998 + [4660, 65535], "active destination/config must stay latched")
    equal(bank_b, [23] * 8000)
    equal(len(transport.started), 1, "Execute edge while Busy cannot queue another transaction")
    equal(transport.started[0][1], bytes.fromhex("03 0000 0002"))
    engine.update("r", changed, False, False, 4, bank_b)
    equal(state(engine.update("r", changed, True, False, 5, bank_b)), BUSY)
    equal(state(engine.update("r", changed, True, False, 7, bank_b)), DONE)
    equal(transport.started[1][1], bytes.fromhex("03 0003 0001"))
    equal(bank_b, [7] + [23] * 7999)
    return {"requests": [entry[1].hex() for entry in transport.started], "destination_tails": [bank_a[-2:], bank_b[:2]]}


def _engine_protocol_atomicity(work):
    from m200.modbus import ModbusConfig, CommunicationEngine

    observed = []
    for response, expected_errors in [("03 04 0001", [0, 2]), ("83 02", [254, 2]), ("04 04 0001 0002", [0, 2])]:
        transport = ScriptedTransport([bytes.fromhex(response)])
        engine, config, words = CommunicationEngine(transport), ModbusConfig(quantity=2, index_data=7998), [101] * 8000
        engine.update("r", config, False, False, 0, words)
        equal(state(engine.update("r", config, True, False, 1, words)), BUSY)
        result = state(engine.update("r", config, True, False, 2, words))
        equal(result, [False, False, False, True, *expected_errors])
        equal(words, [101] * 8000, "invalid or exception response cannot partially commit")
        equal(len(transport.started), 1)
        observed.append({"response_hex": response, "status": result})
    return {"replies": observed}


def _engine_timeout_abort(work):
    from m200.modbus import ModbusConfig, CommunicationEngine

    config = ModbusConfig(timeout_100ms=1, index_data=7999)
    transport, words = ScriptedTransport([None]), [55] * 8000
    engine = CommunicationEngine(transport)
    engine.update("r", config, False, False, 0, words)
    equal(state(engine.update("r", config, True, False, 1, words)), BUSY)
    equal(state(engine.update("r", config, True, False, 100, words)), BUSY)
    equal(state(engine.update("r", config, True, False, 101, words)), [False, False, False, True, 1, 0])
    equal(transport.cancelled, [0])
    equal(words, [55] * 8000)
    no_timeout = replace(config, timeout_100ms=0)
    transport = ScriptedTransport([None])
    engine = CommunicationEngine(transport)
    engine.update("r", no_timeout, False, False, 0, words)
    engine.update("r", no_timeout, True, False, 1, words)
    equal(state(engine.update("r", no_timeout, True, False, 10_000_000, words)), BUSY)
    equal(state(engine.update("r", no_timeout, True, True, 10_000_001, words)), [False, False, True, False, 2, 0])
    equal(state(engine.update("r", no_timeout, True, True, 10_000_002, words)), [False, False, True, False, 2, 0])
    equal(transport.cancelled, [0])
    equal(words, [55] * 8000)
    return {"timeout_boundary_ms": 101, "no_timeout_still_busy_at_ms": 10_000_000, "abort_cancellations": transport.cancelled}


def _engine_channel_arbitration(work):
    from m200.modbus import ModbusConfig, CommunicationEngine

    transport = ScriptedTransport([None, None, None])
    engine, words = CommunicationEngine(transport), [0] * 8000
    first = ModbusConfig(link="SL1", index_data=100)
    second, ethernet = replace(first, index_data=200), replace(first, link="ETH1", index_data=300)
    for key, config in [("first", first), ("second", second), ("ethernet", ethernet)]:
        engine.update(key, config, False, False, 0, words)
    equal(state(engine.update("first", first, True, False, 1, words)), BUSY)
    equal(state(engine.update("second", second, True, False, 1, words)), [False, False, False, True, 255, 11])
    equal(state(engine.update("ethernet", ethernet, True, False, 1, words)), BUSY)
    equal(len(transport.started), 2)
    equal(state(engine.update("first", first, True, True, 2, words)), [False, False, True, False, 2, 0])
    engine.update("second", second, False, False, 3, words)
    equal(state(engine.update("second", second, True, False, 4, words)), BUSY)
    equal([entry[0].link for entry in transport.started], ["SL1", "ETH1", "SL1"])
    return {"local_policy": "one exchange per link; refused occupied link 255/11; no queue/retry", "starts": len(transport.started)}


def cases():
    result = []
    for obj_type, fc in [(2, 1), (1, 2), (0, 3), (3, 4)]:
        result.append(_wire_case(f"G11.wire.read_fc{fc}", {"kind": "READ_VAR", "obj_type": obj_type, "first_obj": 0x1234, "quantity": 2}, {}, f"{fc:02x} 1234 0002"))
    for suffix, config, words, expected in [
        ("single_coil", {"kind": "WRITE_VAR", "obj_type": 4, "first_obj": 7, "index_data": 7999}, {7999: -1}, "05 0007 ff00"),
        ("single_register", {"kind": "WRITE_VAR", "obj_type": 5, "first_obj": 7, "index_data": 7999}, {7999: -32768}, "06 0007 8000"),
        ("packed_coils", {"kind": "WRITE_VAR", "obj_type": 2, "first_obj": 19, "quantity": 10}, {0: 0xFF4D}, "0f 0013 000a 02 4d03"),
        ("holding_words", {"kind": "WRITE_VAR", "first_obj": 0x1234, "quantity": 2, "index_data": 7998}, {7998: 2, 7999: -32767}, "10 1234 0002 04 0002 8001"),
        ("read_write_fc23", {"kind": "WRITE_READ_VAR", "first_obj": 5, "quantity": 2, "first_read_obj": 9, "read_quantity": 3}, {0: 42, 1: -1}, "17 0009 0003 0005 0002 04 002a ffff"),
    ]:
        result.append(_wire_case("G11.wire." + suffix, config, words, expected))
    for suffix, good, bad in [
        ("read_words", {"kind": "READ_VAR", "quantity": 125, "index_data": 7875}, [{"quantity": 126}, {"index_data": 7876}]),
        ("read_bits", {"kind": "READ_VAR", "obj_type": 1, "quantity": 2000, "index_data": 7875}, [{"quantity": 2001}, {"index_data": 7876}]),
        ("write_words", {"kind": "WRITE_VAR", "quantity": 123, "index_data": 7877}, [{"quantity": 124}, {"index_data": 7878}]),
        ("write_bits", {"kind": "WRITE_VAR", "obj_type": 2, "quantity": 1968, "index_data": 7877}, [{"quantity": 1969}, {"index_data": 7878}]),
        ("read_write", {"kind": "WRITE_READ_VAR", "quantity": 121, "index_data": 7879, "read_quantity": 125, "index_data_in": 7875}, [{"quantity": 122}, {"read_quantity": 126}, {"index_data_in": 7876}]),
        ("remote_span", {"kind": "READ_VAR", "first_obj": 65535, "quantity": 1, "index_data": 7999}, [{"first_obj": 65536}, {"quantity": 2}, {"quantity": 0}]),
    ]:
        result.append(_quantity_case("G11.bounds." + suffix, good, bad))
    for identity, description, reference, run in [
        ("G11.responses.atomic_decode", "literal responses, exception codes and rejected padding", PROTOCOL, _responses),
        ("G11.tcp.identity", "MBAP identity, protocol and exact frame length", PROTOCOL, _tcp_identity),
        ("G11.engine.initial_held", "first RUN true is not an edge; terminal lifecycle is literal", FB, _engine_initial_held),
        ("G11.engine.inflight_snapshot", "inflight config and original destination stay latched", FB, _engine_dynamic_snapshot),
        ("G11.engine.protocol_atomicity", "protocol/remote errors never partly commit destination MW", FB, _engine_protocol_atomicity),
        ("G11.engine.timeout_abort", "100ms timeout boundary, no-timeout and abort cancellation", FB, _engine_timeout_abort),
        ("G11.engine.port_arbitration", "same-link contention, independent links and release", FB, _engine_channel_arbitration),
    ]:
        result.append(Case(identity, identity.split(".")[0], description, reference, run))
    return result
