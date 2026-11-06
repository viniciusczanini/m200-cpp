"""Independent Modbus wire fixtures and local-only communication lifecycle tests."""

import dataclasses
import errno
import struct
import socket
import threading
import time
import unittest
from unittest import mock

try:
    from m200 import modbus
except ImportError:
    modbus = None


class ModbusWireTests(unittest.TestCase):
    def config(self, **values):
        self.assertIsNotNone(modbus, "Modbus configuration/protocol module is missing")
        return modbus.ModbusConfig(**values)

    def test_config_validates_limits_and_complete_local_buffer_span(self):
        # Missing validation would permit a response to overwrite shared MW RAM.
        self.config(kind="READ_VAR", obj_type=0, quantity=125, index_data=7875)
        self.config(kind="READ_VAR", obj_type=1, quantity=2000, index_data=7875)
        self.config(kind="WRITE_VAR", obj_type=0, quantity=123, index_data=7877)
        self.config(kind="WRITE_VAR", obj_type=2, quantity=1968, index_data=7877)
        for values in [
            {"quantity": 126},
            {"quantity": 0},
            {"first_obj": 65536},
            {"first_obj": 65535, "quantity": 2},
            {"index_data": 8000},
            {"quantity": 2, "index_data": 7999},
            {"obj_type": 1, "quantity": 17, "index_data": 7999},
            {"obj_type": 1, "quantity": 2001},
            {"timeout_100ms": -1},
            {"id": True},
            {"quantity": 1.0},
            {"obj_type": "0"},
            {"kind": "OTHER"},
            {"link": "SL2"},
        ]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.config(**{"kind": "READ_VAR", **values})

    def test_serial_broadcast_only_permitted_for_write_and_ethernet_is_index(self):
        self.config(kind="WRITE_VAR", link="SL1", id=0)
        self.config(kind="READ_VAR", link="SL1", id=247)
        self.config(kind="READ_VAR", link="ETH1", id=16)
        for values in [
            {"kind": "READ_VAR", "link": "SL1", "id": 0},
            {"kind": "WRITE_READ_VAR", "link": "SL1", "id": 0},
            {"kind": "WRITE_VAR", "link": "ETH1", "id": 0},
            {"kind": "READ_VAR", "link": "ETH1", "id": 17},
            {"kind": "WRITE_VAR", "link": "SL1", "id": 248},
        ]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.config(**values)

    def test_write_read_independent_buffers_and_distinct_121_word_limit(self):
        config = self.config(
            kind="WRITE_READ_VAR",
            quantity=121,
            index_data=7879,
            read_quantity=125,
            index_data_in=7875,
        )
        self.assertEqual(config.read_quantity, 125)
        for values in [
            {"quantity": 122},
            {"read_quantity": 126},
            {"read_quantity": 2, "index_data_in": 7999},
            {"first_read_obj": 65535, "read_quantity": 2},
            {"obj_type": 1},
        ]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.config(kind="WRITE_READ_VAR", **values)

    def test_config_round_trip_is_immutable_and_rejects_unknown_or_coerced_fields(self):
        config = self.config(kind="READ_VAR", link="ETH1", id=3, index_data=20)
        self.assertEqual(modbus.ModbusConfig.from_dict(config.to_dict()), config)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            config.id = 7
        for payload in [
            {**config.to_dict(), "unknown": 1},
            {**config.to_dict(), "quantity": "3"},
            [],
            None,
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                modbus.ModbusConfig.from_dict(payload)

    def test_timeout_respects_int32_representation_in_config_and_json(self):
        # The project XML and SDK constructor store Timeout as signed Int32.
        # Accepting a larger Python integer would break reverse C++ output.
        for kind in ("READ_VAR", "WRITE_VAR", "WRITE_READ_VAR"):
            with self.subTest(kind=kind):
                zero = self.config(kind=kind, timeout_100ms=0)
                maximum = self.config(kind=kind, timeout_100ms=2147483647)
                self.assertEqual(modbus.ModbusConfig.from_dict(zero.to_dict()), zero)
                self.assertEqual(
                    modbus.ModbusConfig.from_dict(maximum.to_dict()), maximum
                )
                for timeout in (2147483648, 4294967295, 9223372036854775807):
                    with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                        self.config(kind=kind, timeout_100ms=timeout)
                    payload = {**maximum.to_dict(), "timeout_100ms": timeout}
                    with (
                        self.subTest(json_timeout=timeout),
                        self.assertRaises(ValueError),
                    ):
                        modbus.ModbusConfig.from_dict(payload)

    def test_read_function_codes_and_request_endianness(self):
        for obj_type, expected_fc in [(0, 3), (1, 2), (2, 1), (3, 4)]:
            config = self.config(
                kind="READ_VAR", obj_type=obj_type, first_obj=0x1234, quantity=2
            )
            self.assertEqual(
                modbus.encode_request(config, [0] * 8000),
                bytes([expected_fc, 0x12, 0x34, 0, 2]),
            )

    def test_register_write_preserves_word_order_and_unsigned_bit_patterns(self):
        config = self.config(
            kind="WRITE_VAR", first_obj=0x1234, quantity=2, index_data=10
        )
        words = [0] * 8000
        words[10:12] = [0x0002, 0x8001]
        self.assertEqual(
            modbus.encode_request(config, words),
            bytes.fromhex("10 1234 0002 04 0002 8001"),
        )
        words[10:12] = [-1, 0]
        self.assertEqual(
            modbus.encode_request(config, words)[6:], bytes.fromhex("ffff 0000")
        )

    def test_coil_write_packing_is_lsb_first_and_clears_unused_padding(self):
        config = self.config(kind="WRITE_VAR", obj_type=2, first_obj=19, quantity=10)
        self.assertEqual(
            modbus.encode_request(config, [0xFF4D] + [0] * 7999),
            bytes.fromhex("0f 0013 000a 02 4d03"),
        )

    def test_single_write_ignores_quantity_and_uses_bit_zero(self):
        coil = self.config(
            kind="WRITE_VAR", obj_type=4, first_obj=7, quantity=0, index_data=7999
        )
        register = self.config(
            kind="WRITE_VAR", obj_type=5, first_obj=9, quantity=65535, index_data=7999
        )
        words = [0] * 7999 + [0x8001]
        self.assertEqual(
            modbus.encode_request(coil, words), bytes.fromhex("05 0007 ff00")
        )
        self.assertEqual(
            modbus.encode_request(register, words), bytes.fromhex("06 0009 8001")
        )
        words[-1] = 2
        self.assertEqual(
            modbus.encode_request(coil, words), bytes.fromhex("05 0007 0000")
        )

    def test_write_read_pdu_and_read_response_use_independent_addresses(self):
        config = self.config(
            kind="WRITE_READ_VAR",
            first_obj=4,
            quantity=2,
            index_data=10,
            first_read_obj=9,
            read_quantity=1,
            index_data_in=20,
        )
        words = [0] * 8000
        words[10:12] = [0x1234, 0x5678]
        request = modbus.encode_request(config, words)
        self.assertEqual(request, bytes.fromhex("17 0009 0001 0004 0002 04 1234 5678"))
        self.assertEqual(
            modbus.decode_response(config, request, bytes.fromhex("17 02 abcd")),
            (0xABCD,),
        )

    def test_read_response_requires_exact_function_length_and_byte_count(self):
        config = self.config(kind="READ_VAR", quantity=2)
        request = modbus.encode_request(config, [0] * 8000)
        self.assertEqual(
            modbus.decode_response(config, request, bytes.fromhex("03 04 8001 ffff")),
            (0x8001, 0xFFFF),
        )
        for response in [
            b"",
            bytes.fromhex("04 04 0001 0002"),
            bytes.fromhex("03 02 0001"),
            bytes.fromhex("03 04 0001"),
            bytes.fromhex("03 04 0001 0002 00"),
        ]:
            with (
                self.subTest(response=response),
                self.assertRaises(modbus.ModbusProtocolError),
            ):
                modbus.decode_response(config, request, response)

    def test_read_bits_packs_into_words_without_leaking_response_padding(self):
        config = self.config(kind="READ_VAR", obj_type=2, quantity=17)
        request = modbus.encode_request(config, [0] * 8000)
        self.assertEqual(
            modbus.decode_response(config, request, bytes.fromhex("01 03 018001")),
            (0x8001, 1),
        )

    def test_write_response_must_echo_requested_address_quantity_or_value(self):
        for obj_type, quantity in [(0, 2), (2, 10), (4, 1), (5, 1)]:
            config = self.config(
                kind="WRITE_VAR", obj_type=obj_type, first_obj=7, quantity=quantity
            )
            request = modbus.encode_request(config, [1] * 8000)
            response = request[:5]
            self.assertEqual(modbus.decode_response(config, request, response), ())
            for corrupt in [response + b"\0", response[:2] + b"\1" + response[3:]]:
                with (
                    self.subTest(corrupt=corrupt),
                    self.assertRaises(modbus.ModbusProtocolError),
                ):
                    modbus.decode_response(config, request, corrupt)

    def test_nonzero_unused_read_bits_are_malformed_not_silent_extra_values(self):
        config = self.config(kind="READ_VAR", obj_type=2, quantity=17)
        request = modbus.encode_request(config)
        with self.assertRaises(modbus.ModbusProtocolError):
            modbus.decode_response(config, request, bytes.fromhex("01 03 018003"))

    def test_mbap_expected_identity_must_be_exact_integers(self):
        self.config()
        frame = bytes.fromhex("0001 0000 0005 01 03021234")
        for transaction, unit in [(True, 1), (1, True), (1.0, 1), (1, 1.0)]:
            with (
                self.subTest(transaction=transaction, unit=unit),
                self.assertRaises(ValueError),
            ):
                modbus.decode_tcp(frame, transaction_id=transaction, unit_id=unit)

    def test_write_rejects_unsupported_types_and_outside_protocol_limits(self):
        self.config(kind="WRITE_VAR", first_obj=65535, obj_type=5, index_data=7999)
        for values in [
            {"obj_type": 1},
            {"obj_type": 3},
            {"quantity": 124},
            {"obj_type": 2, "quantity": 1969},
            {"obj_type": 2, "quantity": 17, "index_data": 7999},
        ]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.config(**{"kind": "WRITE_VAR", **values})

    def test_modbus_exception_retains_communication_and_operation_codes(self):
        config = self.config(kind="READ_VAR")
        request = modbus.encode_request(config, [0] * 8000)
        with self.assertRaises(modbus.ModbusExceptionResponse) as caught:
            modbus.decode_response(config, request, bytes.fromhex("83 02"))
        self.assertEqual(caught.exception.comm_error, 254)
        self.assertEqual(caught.exception.oper_error, 2)
        for invalid in [
            bytes.fromhex("84 02"),
            bytes.fromhex("83 02 00"),
            bytes.fromhex("83 00"),
        ]:
            with self.assertRaises(modbus.ModbusProtocolError):
                modbus.decode_response(config, request, invalid)

    def test_mbap_checks_transaction_unit_protocol_and_exact_length(self):
        self.config()
        pdu = bytes.fromhex("03 02 1234")
        frame = modbus.encode_tcp(0x1234, 7, pdu)
        self.assertEqual(frame, bytes.fromhex("1234 0000 0005 07 03021234"))
        self.assertEqual(
            modbus.decode_tcp(frame, transaction_id=0x1234, unit_id=7), pdu
        )
        for corrupt in [
            frame[:5],
            frame + b"\0",
            frame[:-1],
            bytes.fromhex("1235") + frame[2:],
            frame[:3] + b"\1" + frame[4:],
            frame[:6] + b"\x08" + frame[7:],
            frame[:4] + bytes.fromhex("ffff") + frame[6:],
        ]:
            with (
                self.subTest(corrupt=corrupt),
                self.assertRaises(modbus.ModbusProtocolError),
            ):
                modbus.decode_tcp(corrupt, transaction_id=0x1234, unit_id=7)


class ModbusEngineTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(modbus)
        self.assertTrue(
            hasattr(modbus, "CommunicationEngine"), "asynchronous engine missing"
        )
        self.peer = modbus.MemoryModbusPeer(
            holding_registers=[0] * 128,
            input_registers=[0] * 128,
            coils=[False] * 128,
            discrete_inputs=[False] * 128,
        )
        self.transport = modbus.MemoryTransport(self.peer, latency_ms=10)
        self.engine = modbus.CommunicationEngine(self.transport)
        self.words = [0] * 8000
        self.read = modbus.ModbusConfig(
            kind="READ_VAR", first_obj=3, quantity=2, index_data=10
        )

    def update(self, execute, abort=False, now=0, key="read", config=None):
        return self.engine.update(
            key, config or self.read, execute, abort, now, self.words
        )

    def test_first_run_true_is_not_an_edge_and_status_read_has_no_side_effect(self):
        self.peer.holding_registers[3:5] = [0x0002, 0x8001]
        self.assertEqual(self.engine.status("unknown"), modbus.CommunicationStatus())
        self.assertFalse(self.update(True).busy)
        self.assertFalse(self.update(True, now=1).busy)
        self.update(False, now=2)
        self.assertTrue(self.update(True, now=3).busy)
        self.assertEqual(self.words[10:12], [0, 0])
        self.assertTrue(self.update(True, now=13).done)
        self.assertEqual(self.words[10:12], [2, 0x8001])
        self.assertTrue(self.engine.status("read").done)
        self.assertTrue(self.engine.status("read").done)

    def test_completion_latches_while_execute_true_then_clears_on_false(self):
        self.update(False)
        self.update(True, now=1)
        self.assertTrue(self.update(True, now=11).done)
        self.assertTrue(self.update(True, now=12).done)
        status = self.update(False, now=13)
        self.assertEqual(status, modbus.CommunicationStatus())

    def test_completion_is_one_update_pulse_if_execute_already_false(self):
        self.update(False)
        self.update(True, now=1)
        self.assertTrue(self.update(False, now=2).busy)
        self.assertTrue(self.update(False, now=11).done)
        self.assertEqual(self.update(False, now=12), modbus.CommunicationStatus())

    def test_second_execute_edge_and_configuration_changes_are_ignored_while_busy(self):
        self.peer.holding_registers[3:5] = [11, 22]
        self.peer.holding_registers[7:9] = [33, 44]
        self.update(False)
        self.update(True, now=1)
        self.update(False, now=2)
        changed = dataclasses.replace(self.read, first_obj=7, index_data=20)
        self.assertTrue(self.update(True, now=3, config=changed).busy)
        self.assertTrue(self.update(True, now=11, config=changed).done)
        self.assertEqual(self.words[10:12], [11, 22])
        self.assertEqual(self.words[20:22], [0, 0])
        self.assertTrue(self.update(True, now=30, config=changed).done)
        self.assertEqual(self.words[20:22], [0, 0])

    def test_abort_rising_edge_cancels_without_error_or_late_memory_write(self):
        self.peer.holding_registers[3:5] = [77, 88]
        self.update(False, abort=True)
        self.assertTrue(self.update(True, abort=True, now=1).busy)
        self.update(True, abort=False, now=2)
        status = self.update(True, abort=True, now=3)
        self.assertTrue(status.aborted)
        self.assertFalse(status.error)
        self.assertFalse(status.busy)
        self.assertEqual((status.comm_error, status.oper_error), (2, 0))
        self.assertTrue(self.update(True, abort=True, now=100).aborted)
        self.assertEqual(self.words[10:12], [0, 0])

    def test_abort_wins_over_simultaneous_execute_edge_as_local_safety_policy(self):
        self.update(False)
        self.assertEqual(
            self.update(True, abort=True, now=1), modbus.CommunicationStatus()
        )
        self.assertEqual(self.words[10:12], [0, 0])

    def test_timeout_boundary_is_integer_exact_and_late_response_is_ignored(self):
        self.transport = modbus.MemoryTransport(self.peer, latency_ms=100)
        self.engine = modbus.CommunicationEngine(self.transport)
        config = dataclasses.replace(self.read, timeout_100ms=1)
        self.peer.holding_registers[3:5] = [77, 88]
        self.update(False, config=config)
        self.assertTrue(self.update(True, now=1, config=config).busy)
        self.assertTrue(self.update(True, now=100, config=config).busy)
        status = self.update(True, now=101, config=config)
        self.assertTrue(status.error)
        self.assertEqual((status.comm_error, status.oper_error), (1, 0))
        self.assertFalse(self.update(True, now=1000, config=config).done)
        self.assertEqual(self.words[10:12], [0, 0])

    def test_timeout_zero_waits_without_forcing_success(self):
        self.transport = modbus.MemoryTransport(self.peer, latency_ms=100_000)
        self.engine = modbus.CommunicationEngine(self.transport)
        config = dataclasses.replace(self.read, timeout_100ms=0)
        self.update(False, config=config)
        self.update(True, now=1, config=config)
        self.assertTrue(self.update(True, now=99_999, config=config).busy)
        self.assertTrue(self.update(True, now=100_001, config=config).done)

    def test_one_exchange_per_link_and_release_after_abort(self):
        second = dataclasses.replace(self.read, index_data=20)
        ethernet = dataclasses.replace(self.read, link="ETH1", index_data=30)
        self.update(False)
        self.update(False, key="second", config=second)
        self.update(False, key="ethernet", config=ethernet)
        self.update(True, now=1)
        refused = self.update(True, key="second", now=1, config=second)
        self.assertTrue(refused.error)
        self.assertEqual((refused.comm_error, refused.oper_error), (255, 11))
        self.assertTrue(self.update(True, key="ethernet", now=1, config=ethernet).busy)
        self.assertTrue(self.update(True, abort=True, now=2).aborted)
        self.update(False, key="second", now=2, config=second)
        self.assertTrue(self.update(True, key="second", now=3, config=second).busy)

    def test_no_transport_produces_explicit_channel_error_never_fake_success(self):
        self.engine = modbus.CommunicationEngine()
        self.update(False)
        status = self.update(True, now=1)
        self.assertTrue(status.error)
        self.assertFalse(status.done)
        self.assertEqual((status.comm_error, status.oper_error), (255, 15))
        self.assertEqual(self.words[10:12], [0, 0])

    def test_modbus_peer_illegal_address_propagates_exception_codes(self):
        config = dataclasses.replace(self.read, first_obj=127)
        self.update(False, config=config)
        self.update(True, now=1, config=config)
        status = self.update(True, now=11, config=config)
        self.assertTrue(status.error)
        self.assertEqual((status.comm_error, status.oper_error), (254, 2))
        self.assertEqual(self.words[10:12], [0, 0])

    def test_read_words_share_dword_and_float_bit_patterns_without_swapping(self):
        config = dataclasses.replace(self.read, first_obj=0, quantity=4, index_data=0)
        self.peer.holding_registers[:4] = [2, 1, 0, 0x3F80]
        self.update(False, config=config)
        self.update(True, now=1, config=config)
        self.assertTrue(self.update(True, now=11, config=config).done)
        self.assertEqual(self.words[:4], [2, 1, 0, 0x3F80])
        self.assertEqual(
            struct.unpack("<i", struct.pack("<HH", *self.words[:2]))[0], 65538
        )
        self.assertEqual(
            struct.unpack("<f", struct.pack("<HH", *self.words[2:4]))[0], 1.0
        )

    def test_write_captures_source_words_on_execute_not_during_later_poll(self):
        config = modbus.ModbusConfig(
            kind="WRITE_VAR", first_obj=5, quantity=2, index_data=10
        )
        self.words[10:12] = [0x1234, 0xABCD]
        self.update(False, config=config)
        self.update(True, now=1, config=config)
        self.words[10:12] = [9, 9]
        self.assertTrue(self.update(True, now=11, config=config).done)
        self.assertEqual(self.peer.holding_registers[5:7], [0x1234, 0xABCD])

    def test_write_read_performs_write_before_read_and_supports_buffer_overlap(self):
        config = modbus.ModbusConfig(
            kind="WRITE_READ_VAR",
            first_obj=5,
            quantity=2,
            index_data=10,
            first_read_obj=5,
            read_quantity=2,
            index_data_in=11,
        )
        self.words[10:12] = [0x1234, 0xABCD]
        self.update(False, config=config)
        self.update(True, now=1, config=config)
        self.assertTrue(self.update(True, now=11, config=config).done)
        self.assertEqual(self.peer.holding_registers[5:7], [0x1234, 0xABCD])
        self.assertEqual(self.words[10:13], [0x1234, 0x1234, 0xABCD])

    def test_broadcast_done_requires_transport_confirming_send_not_a_response(self):
        config = modbus.ModbusConfig(kind="WRITE_VAR", id=0, first_obj=5, obj_type=5)
        self.words[0] = 0xFEDC
        self.update(False, config=config)
        self.assertTrue(self.update(True, now=1, config=config).busy)
        self.assertTrue(self.update(True, now=11, config=config).done)
        self.assertEqual(self.peer.holding_registers[5], 0xFEDC)

    def test_clock_and_boolean_inputs_fail_closed_instead_of_losing_edges(self):
        self.update(False, now=100)
        for execute, now in [(0, 101), (False, 1), (False, 100.5), (False, True)]:
            with self.subTest(execute=execute, now=now), self.assertRaises(ValueError):
                self.update(execute, now=now)


class ModbusPeerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(modbus)
        self.assertTrue(
            hasattr(modbus, "MemoryModbusPeer"), "local protocol peer missing"
        )
        self.peer = modbus.MemoryModbusPeer(
            holding_registers=[0x1234, 0x5678],
            input_registers=[0xABCD, 0xEF01],
            coils=[True, False, True],
            discrete_inputs=[False, True, False],
        )

    def test_peer_uses_separate_modbus_address_spaces(self):
        for request, response in [
            ("03 0000 0002", "03 04 1234 5678"),
            ("04 0000 0002", "04 04 abcd ef01"),
            ("01 0000 0003", "01 01 05"),
            ("02 0000 0003", "02 01 02"),
        ]:
            with self.subTest(request=request):
                self.assertEqual(
                    self.peer.handle_request(bytes.fromhex(request)),
                    bytes.fromhex(response),
                )

    def test_peer_writes_only_requested_coils_and_registers(self):
        self.assertEqual(
            self.peer.handle_request(bytes.fromhex("0f 0000 0002 01 02")),
            bytes.fromhex("0f 0000 0002"),
        )
        self.assertEqual(self.peer.coils, [False, True, True])
        self.assertEqual(
            self.peer.handle_request(bytes.fromhex("10 0000 0002 04 8000 ffff")),
            bytes.fromhex("10 0000 0002"),
        )
        self.assertEqual(self.peer.holding_registers, [0x8000, 0xFFFF])
        self.assertEqual(self.peer.input_registers, [0xABCD, 0xEF01])
        self.assertEqual(
            self.peer.handle_request(bytes.fromhex("05 0000 ff00")),
            bytes.fromhex("05 0000 ff00"),
        )
        self.assertEqual(
            self.peer.handle_request(bytes.fromhex("06 0001 1234")),
            bytes.fromhex("06 0001 1234"),
        )
        self.assertEqual(self.peer.coils, [True, True, True])
        self.assertEqual(self.peer.holding_registers, [0x8000, 0x1234])

    def test_peer_rejects_nonzero_unused_coil_bits_without_mutating(self):
        self.assertEqual(
            self.peer.handle_request(bytes.fromhex("0f 0000 0002 01 86")),
            bytes.fromhex("8f 03"),
        )
        self.assertEqual(self.peer.coils, [True, False, True])

    def test_memory_transport_bounds_and_validates_pending_requests(self):
        transport = modbus.MemoryTransport(self.peer)
        config = modbus.ModbusConfig()
        request = bytes.fromhex("03 0000 0001")
        for pdu in [b"", bytes(254), bytearray(request), 10]:
            with self.subTest(pdu=pdu), self.assertRaises(ValueError):
                modbus.MemoryTransport(self.peer).start(config, pdu, 0)
        one = transport.start(config, request, 0)
        two = transport.start(config, request, 0)
        with self.assertRaises(modbus.ModbusTransportError):
            transport.start(config, request, 0)
        transport.cancel(one)
        with self.assertRaises(modbus.ModbusTransportError):
            transport.poll(one, 1)
        self.assertEqual(transport.poll(two, 1), bytes.fromhex("03 02 1234"))

    def test_peer_refuses_malformed_unsupported_and_out_of_range_requests_atomically(
        self,
    ):
        for request, response in [
            ("03 0001 0002", "83 02"),
            ("03 0000 0000", "83 03"),
            ("03 0000 0001 00", "83 03"),
            ("07", "87 01"),
            ("05 0000 0001", "85 03"),
            ("10 0000 0002 02 1234", "90 03"),
            ("10 0001 0002 04 1234 5678", "90 02"),
            ("17 0002 0001 0000 0001 02 aaaa", "97 02"),
        ]:
            with self.subTest(request=request):
                self.assertEqual(
                    self.peer.handle_request(bytes.fromhex(request)),
                    bytes.fromhex(response),
                )
                self.assertEqual(self.peer.holding_registers, [0x1234, 0x5678])
                self.assertEqual(self.peer.coils, [True, False, True])


class _LoopbackPeerServer:
    """Test fixture: accepts loopback only and deliberately fragments responses."""

    def __init__(self, peer, transform=None, silent=False):
        self.peer, self.transform, self.silent = peer, transform, silent
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.listener.listen(2)
        self.listener.settimeout(0.05)
        self.stopped = threading.Event()
        self.received = threading.Event()
        self.errors = []
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *unused):
        self.stopped.set()
        self.thread.join(timeout=1)
        self.listener.close()
        if self.thread.is_alive():
            raise AssertionError("loopback peer did not stop")
        if self.errors:
            raise AssertionError(self.errors)

    @staticmethod
    def exact(client, length):
        data = b""
        while len(data) < length:
            more = client.recv(length - len(data))
            if not more:
                raise EOFError("test client closed before a complete request")
            data += more
        return data

    def serve(self):
        try:
            while not self.stopped.is_set():
                try:
                    client, _ = self.listener.accept()
                except socket.timeout:
                    continue
                with client:
                    client.settimeout(0.5)
                    header = self.exact(client, 7)
                    transaction, protocol, length, unit = struct.unpack(">HHHB", header)
                    if protocol != 0 or not 2 <= length <= 254:
                        raise AssertionError("invalid outgoing MBAP header")
                    request = self.exact(client, length - 1)
                    self.received.set()
                    if self.silent:
                        self.stopped.wait(timeout=0.5)
                        continue
                    response = modbus.encode_tcp(
                        transaction, unit, self.peer.handle_request(request)
                    )
                    if self.transform:
                        response = self.transform(response)
                    # Three sends exercise a TCP stream without message boundaries.
                    for part in (response[:2], response[2:5], response[5:]):
                        client.sendall(part)
                        time.sleep(0.002)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except BaseException as error:
            self.errors.append(error)


class ModbusLoopbackTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(modbus)
        self.assertTrue(
            hasattr(modbus, "LoopbackTCPTransport"),
            "explicit loopback TCP transport missing",
        )
        self.peer = modbus.MemoryModbusPeer(holding_registers=[0] * 128)
        self.config = modbus.ModbusConfig(
            kind="READ_VAR", link="ETH1", id=1, first_obj=3, quantity=2, index_data=10
        )
        self.words = [0] * 8000

    def exchange(self, transport, config=None):
        config = config or self.config
        engine = modbus.CommunicationEngine(transport)
        engine.update("tcp", config, False, False, 0, self.words)
        status = engine.update("tcp", config, True, False, 1, self.words)
        started = time.monotonic()
        while status.busy and time.monotonic() - started < 2:
            time.sleep(0.001)
            now = 1 + int((time.monotonic() - started) * 1000)
            status = engine.update("tcp", config, True, False, now, self.words)
        self.assertFalse(
            status.busy, "local transport must terminate within test deadline"
        )
        return status

    def test_transport_rejects_non_loopback_and_hostnames_before_any_connection(self):
        for host in ["192.0.2.1", "8.8.8.8", "localhost", "example.com", "::1"]:
            with self.subTest(host=host), self.assertRaises(ValueError):
                modbus.LoopbackTCPTransport(host=host, port=502)
        for port in [0, 65536, True, "502"]:
            with self.subTest(port=port), self.assertRaises(ValueError):
                modbus.LoopbackTCPTransport(port=port)

    def test_socket_creation_exhaustion_becomes_channel_error_without_network_io(self):
        transport = modbus.LoopbackTCPTransport(port=1)
        self.addCleanup(transport.close)
        engine = modbus.CommunicationEngine(transport)
        engine.update("tcp", self.config, False, False, 0, self.words)
        with mock.patch(
            "m200.modbus.socket.socket",
            side_effect=OSError(errno.EMFILE, "too many open files"),
        ):
            status = engine.update("tcp", self.config, True, False, 1, self.words)
        self.assertTrue(status.error)
        self.assertFalse(status.busy)
        self.assertFalse(status.done)
        self.assertEqual((status.comm_error, status.oper_error), (255, 6))
        self.assertEqual(self.words[10:12], [0, 0])

    def test_actual_fragmented_loopback_read_uses_explicit_unit_not_ethernet_index(
        self,
    ):
        self.peer.holding_registers[3:5] = [0x0002, 0x8001]
        with _LoopbackPeerServer(self.peer) as server:
            transport = modbus.LoopbackTCPTransport(port=server.port, unit_id=7)
            self.addCleanup(transport.close)
            status = self.exchange(transport)
            self.assertTrue(server.received.is_set())
            self.assertTrue(status.done)
            self.assertEqual(self.words[10:12], [2, 0x8001])

    def test_actual_loopback_write_and_write_read_mutate_only_requested_peer_words(
        self,
    ):
        with _LoopbackPeerServer(self.peer) as server:
            transport = modbus.LoopbackTCPTransport(port=server.port)
            self.addCleanup(transport.close)
            self.words[10:12] = [0x1234, 0xABCD]
            write = dataclasses.replace(self.config, kind="WRITE_VAR", first_obj=7)
            self.assertTrue(self.exchange(transport, write).done)
            self.assertEqual(self.peer.holding_registers[6:10], [0, 0x1234, 0xABCD, 0])
            rw = dataclasses.replace(
                self.config,
                kind="WRITE_READ_VAR",
                first_obj=7,
                first_read_obj=7,
                read_quantity=2,
                index_data_in=20,
            )
            self.words[10:12] = [0xFEDC, 0x9876]
            self.assertTrue(self.exchange(transport, rw).done)
            self.assertEqual(self.words[20:22], [0xFEDC, 0x9876])
            self.assertEqual(self.peer.holding_registers[7:9], [0xFEDC, 0x9876])

    def test_actual_loopback_bad_identity_protocol_and_length_never_write_memory(self):
        transforms = {
            "transaction": lambda frame: bytes([frame[0] ^ 1]) + frame[1:],
            "unit": lambda frame: frame[:6] + bytes([frame[6] ^ 1]) + frame[7:],
            "protocol": lambda frame: frame[:3] + b"\x01" + frame[4:],
            "long_length": lambda frame: frame[:4] + bytes.fromhex("0008") + frame[6:],
            "short_length": lambda frame: frame[:4] + bytes.fromhex("0002") + frame[6:],
            "over_limit_length": lambda frame: (
                frame[:4] + bytes.fromhex("ffff") + frame[6:]
            ),
            "truncated": lambda frame: frame[:-1],
            "wrong_function": lambda frame: frame[:7] + b"\x04" + frame[8:],
            "wrong_byte_count": lambda frame: frame[:8] + b"\x02" + frame[9:],
        }
        self.peer.holding_registers[3:5] = [11, 22]
        for name, transform in transforms.items():
            with (
                self.subTest(name=name),
                _LoopbackPeerServer(self.peer, transform) as server,
            ):
                transport = modbus.LoopbackTCPTransport(port=server.port)
                try:
                    status = self.exchange(transport)
                    self.assertTrue(status.error)
                    self.assertFalse(status.done)
                    # An unmatched transaction is discarded. This peer then
                    # closes without answering the pending request: channel
                    # failure, rather than a malformed matching response.
                    expected = (255, 6) if name == "transaction" else (0, 2)
                    self.assertEqual((status.comm_error, status.oper_error), expected)
                    self.assertEqual(self.words[10:12], [0, 0])
                finally:
                    transport.close()

    def test_actual_loopback_exception_propagates_without_claiming_completion(self):
        with _LoopbackPeerServer(self.peer) as server:
            transport = modbus.LoopbackTCPTransport(port=server.port)
            self.addCleanup(transport.close)
            status = self.exchange(
                transport, dataclasses.replace(self.config, first_obj=127)
            )
            self.assertTrue(status.error)
            self.assertFalse(status.done)
            self.assertEqual((status.comm_error, status.oper_error), (254, 2))

    def test_actual_loopback_silent_peer_times_out_and_closes_exchange(self):
        with _LoopbackPeerServer(self.peer, silent=True) as server:
            transport = modbus.LoopbackTCPTransport(port=server.port)
            self.addCleanup(transport.close)
            status = self.exchange(
                transport, dataclasses.replace(self.config, timeout_100ms=1)
            )
            self.assertTrue(server.received.is_set())
            self.assertTrue(status.error)
            self.assertEqual((status.comm_error, status.oper_error), (1, 0))
            self.assertEqual(self.words[10:12], [0, 0])

    def test_actual_loopback_abort_cancels_exchange_without_success(self):
        with _LoopbackPeerServer(self.peer, silent=True) as server:
            transport = modbus.LoopbackTCPTransport(port=server.port)
            self.addCleanup(transport.close)
            engine = modbus.CommunicationEngine(transport)
            engine.update("tcp", self.config, False, False, 0, self.words)
            status = engine.update("tcp", self.config, True, False, 1, self.words)
            for now in range(2, 102):
                status = engine.update("tcp", self.config, True, False, now, self.words)
                if server.received.wait(timeout=0.001):
                    break
            self.assertTrue(server.received.is_set())
            self.assertTrue(status.busy)
            status = engine.update("tcp", self.config, True, True, 102, self.words)
            self.assertTrue(status.aborted)
            self.assertFalse(status.done)
            self.assertEqual(status.comm_error, 2)

    def test_transport_refuses_serial_or_unconfigured_remote_index(self):
        transport = modbus.LoopbackTCPTransport(port=502)
        self.addCleanup(transport.close)
        for config in [
            dataclasses.replace(self.config, link="SL1"),
            dataclasses.replace(self.config, id=2),
        ]:
            with (
                self.subTest(config=config),
                self.assertRaises(modbus.ModbusTransportError),
            ):
                transport.start(config, modbus.encode_request(config), 0)


if __name__ == "__main__":
    unittest.main()
