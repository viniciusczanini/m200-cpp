"""Real ephemeral-loopback regressions for bounded stale-frame recovery."""

import socket
import struct
import threading
import time
import unittest

from m200.modbus import CommunicationEngine, LoopbackTCPTransport, ModbusConfig


class ScriptedLoopbackServer:
    def __init__(self, scripts):
        self.scripts = scripts
        self.stop = threading.Event()
        self.release = threading.Event()
        self.sent = threading.Event()
        self.errors = []
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.listener.listen(1)
        self.listener.settimeout(0.05)
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *unused):
        self.stop.set()
        self.release.set()
        self.thread.join(2)
        self.listener.close()
        if self.thread.is_alive() or self.errors:
            raise AssertionError((self.thread.is_alive(), self.errors))

    @staticmethod
    def exact(client, count):
        result = b""
        while len(result) < count:
            part = client.recv(count - len(result))
            if not part:
                raise EOFError("Incomplete test request")
            result += part
        return result

    @staticmethod
    def frame(tid, unit, pdu=bytes.fromhex("03 04 12 34 ab cd")):
        return struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu

    def serve(self):
        for script in self.scripts:
            try:
                while not self.stop.is_set():
                    try:
                        client, _ = self.listener.accept()
                        break
                    except socket.timeout:
                        continue
                else:
                    return
                with client:
                    client.settimeout(1)
                    tid, protocol, size, unit = struct.unpack(
                        ">HHHB", self.exact(client, 7)
                    )
                    request = self.exact(client, size - 1)
                    if protocol != 0 or request != bytes.fromhex("03 0003 0002"):
                        raise AssertionError((protocol, request))
                    script(self, client, tid, unit)
            except (BrokenPipeError, ConnectionResetError):
                continue
            except BaseException as error:
                self.errors.append(error)
                return


class ModbusTransportRecoveryTests(unittest.TestCase):
    def connect(self, server, timeout=100):
        self.config = ModbusConfig(
            link="ETH1", first_obj=3, quantity=2, index_data=10, timeout_100ms=timeout
        )
        self.words = [0] * 8000
        self.words[9:13] = [0x1111, 0x2222, 0x3333, 0x4444]
        self.transport = LoopbackTCPTransport(port=server.port, unit_id=7)
        self.addCleanup(self.transport.close)
        self.engine = CommunicationEngine(self.transport)
        self.now = 0
        self.step(False)

    def step(self, execute=True, now=None):
        if now is not None:
            self.now = now
        return self.engine.update(
            "read", self.config, execute, False, self.now, self.words
        )

    def until(self, predicate):
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            status = self.step()
            if predicate(status):
                return status
            time.sleep(0.001)
        self.fail("Loopback exchange exceeded bounded test deadline")

    def assert_recovered(self):
        self.step(False)
        status = self.until(lambda s: not s.busy)
        self.assertTrue(status.done)
        self.assertFalse(status.error)
        self.assertEqual(self.words[9:13], [0x1111, 0x1234, 0xABCD, 0x4444])

    def test_unknown_transaction_is_discarded_before_fragmented_current_reply(self):
        def script(server, client, tid, unit):
            client.sendall(
                server.frame(tid ^ 0x8000, unit, bytes.fromhex("03 04 de ad be ef"))
            )
            server.sent.set()
            if not server.release.wait(1):
                return
            reply = server.frame(tid, unit)
            for part in (reply[:2], reply[2:7], reply[7:]):
                client.sendall(part)

        with ScriptedLoopbackServer([script]) as server:
            self.connect(server)
            self.until(lambda s: server.sent.is_set())
            for _ in range(5):
                status = self.step()
            self.assertTrue(
                status.busy,
                "An unrelated response must not terminate the pending transaction",
            )
            self.assertFalse(status.error)
            self.assertEqual(self.words[9:13], [0x1111, 0x2222, 0x3333, 0x4444])
            server.release.set()
            self.assertTrue(self.until(lambda s: not s.busy).done)
            self.assertEqual(self.words[9:13], [0x1111, 0x1234, 0xABCD, 0x4444])

    def test_coalesced_stale_and_current_adus_are_framed_independently(self):
        def script(server, client, tid, unit):
            # Maximum legal MBAP frame length, unrelated to this request.
            stale = server.frame(tid ^ 0x8000, unit, b"\x03" + b"\x00" * 252)
            client.sendall(stale + server.frame(tid, unit))

        with ScriptedLoopbackServer([script]) as server:
            self.connect(server)
            self.assertTrue(self.until(lambda s: not s.busy).done)
            self.assertEqual(self.words[10:12], [0x1234, 0xABCD])

    def test_only_unmatched_reply_waits_for_timeout_then_new_edge_reconnects(self):
        def stale(server, client, tid, unit):
            client.sendall(server.frame(tid ^ 0x8000, unit))
            server.sent.set()
            server.release.wait(1)

        def valid(server, client, tid, unit):
            client.sendall(server.frame(tid, unit))

        with ScriptedLoopbackServer([stale, valid]) as server:
            self.connect(server, timeout=1)
            self.until(lambda s: server.sent.is_set())
            for _ in range(5):
                status = self.step()
            self.assertTrue(status.busy)
            status = self.step(now=100)
            self.assertEqual((status.comm_error, status.oper_error), (1, 0))
            self.assertFalse(status.done)
            self.assertEqual(self.words[10:12], [0x2222, 0x3333])
            server.release.set()
            self.assert_recovered()

    def test_unmatched_frame_flood_is_bounded_and_next_exchange_recovers(self):
        def flood(server, client, tid, unit):
            client.sendall(server.frame(tid ^ 0x8000, unit) * 17)

        def valid(server, client, tid, unit):
            client.sendall(server.frame(tid, unit))

        with ScriptedLoopbackServer([flood, valid]) as server:
            self.connect(server, timeout=0)
            status = self.until(lambda s: not s.busy)
            self.assertTrue(status.error)
            self.assertFalse(status.done)
            self.assertEqual((status.comm_error, status.oper_error), (0, 2))
            self.assertEqual(self.words[10:12], [0x2222, 0x3333])
            self.assert_recovered()

    def test_sixteen_unmatched_adus_still_allow_the_pending_response(self):
        def script(server, client, tid, unit):
            client.sendall(
                server.frame(tid ^ 0x8000, unit) * 16 + server.frame(tid, unit)
            )

        with ScriptedLoopbackServer([script]) as server:
            self.connect(server, timeout=0)
            self.assertTrue(self.until(lambda s: not s.busy).done)
            self.assertEqual(self.words[10:12], [0x1234, 0xABCD])

    def test_matched_bad_unit_exception_and_eof_do_not_poison_reconnection(self):
        def bad_unit(server, client, tid, unit):
            client.sendall(server.frame(tid, unit + 1))

        def exception(server, client, tid, unit):
            client.sendall(server.frame(tid, unit, bytes.fromhex("83 02")))

        def truncated(server, client, tid, unit):
            client.sendall(server.frame(tid, unit)[:-1])

        def valid(server, client, tid, unit):
            client.sendall(server.frame(tid, unit))

        with ScriptedLoopbackServer([bad_unit, exception, truncated, valid]) as server:
            self.connect(server)
            for expected in [(0, 2), (254, 2), (0, 2)]:
                status = self.until(lambda s: not s.busy)
                self.assertTrue(status.error)
                self.assertEqual((status.comm_error, status.oper_error), expected)
                self.assertEqual(self.words[10:12], [0x2222, 0x3333])
                self.step(False)
            self.assert_recovered()


if __name__ == "__main__":
    unittest.main()
