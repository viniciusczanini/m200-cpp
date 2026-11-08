"""Local Modbus model; never opens a device connection implicitly.

Configuration, edges, buffer packing and numeric status codes follow Schneider
EIO0000003289.04 pp171-186,204-205. Wire encoding follows Modbus Application
Protocol V1.1b3 sections 6.1-6.6,6.11-6.12,6.17 and TCP implementation guide
V1.0b section 3.1.3. These local tests do not establish TM200 compatibility.
ETH1 Id is a configured remote-server INDEX, not the MBAP unit identifier.
Only embedded SL1/ETH1 are accepted; cartridges are outside this subset.
"""

import errno
import ipaddress
import select
import socket
import struct
from dataclasses import asdict, dataclass, fields

from .model import fail, CompileError
from .communication_properties import initial_properties, effective_config, signed_word, DOMAINS


READ_FUNCTIONS = {0: 3, 1: 2, 2: 1, 3: 4}
WRITE_FUNCTIONS = {0: 16, 2: 15, 4: 5, 5: 6}
EXCEPTION_CODES = frozenset((1, 2, 3, 4, 5, 6, 8, 10, 11))


def _integer(value, name, low, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        fail("invalid Modbus " + name)


def _span(first, count, limit, name):
    if first + count > limit:
        fail("Modbus " + name + " exceeds address space")


@dataclass(frozen=True)
class ModbusConfig:
    kind: str = "READ_VAR"
    link: str = "SL1"
    id: int = 1
    timeout_100ms: int = 100
    obj_type: int = 0
    first_obj: int = 0
    quantity: int = 1
    index_data: int = 0
    # WRITE_READ_VAR: basic fields above describe its write side.
    first_read_obj: int = 0
    read_quantity: int = 1
    index_data_in: int = 0

    def __post_init__(self):
        validate_config(self)

    @property
    def function_code(self):
        if self.kind == "WRITE_READ_VAR":
            return 23
        return (READ_FUNCTIONS if self.kind == "READ_VAR" else WRITE_FUNCTIONS)[
            self.obj_type
        ]

    @property
    def data_words(self):
        if self.function_code in (5, 6):
            return 1
        if self.function_code in (1, 2, 15):
            return (self.quantity + 15) // 16
        return self.quantity

    def to_dict(self):
        return asdict(self)

    as_dict = to_dict

    @classmethod
    def from_dict(cls, data):
        if type(data) is not dict or set(data) - {f.name for f in fields(cls)}:
            fail("invalid or unknown Modbus configuration fields")
        try:
            return cls(**data)
        except TypeError:
            fail("invalid Modbus configuration")


def validate_config(config):
    if not isinstance(config, ModbusConfig):
        fail("Modbus configuration required")
    if config.kind not in ("READ_VAR", "WRITE_VAR", "WRITE_READ_VAR"):
        fail("unsupported Modbus function block")
    if config.link not in ("SL1", "ETH1"):
        fail("unsupported Modbus link; only embedded SL1/ETH1 are modeled")
    minimum = 0 if config.kind == "WRITE_VAR" and config.link == "SL1" else 1
    _integer(config.id, "Id", minimum, 247 if config.link == "SL1" else 16)
    # The authenticated project XML represents Timeout as System.Int32; the
    # SDK constructor uses the same signed range. This is a representation
    # bound, not a separately documented controller timeout maximum.
    _integer(config.timeout_100ms, "Timeout (100 ms units)", 0, 2147483647)
    _integer(config.obj_type, "ObjType", 0, 5)
    _integer(config.first_obj, "FirstObj", 0, 65535)
    _integer(config.index_data, "IndexData", 0, 7999)
    _integer(config.quantity, "Quantity", 0, 65535)
    _integer(config.first_read_obj, "FirstReadObj", 0, 65535)
    _integer(config.read_quantity, "ReadQuantity", 1, 125)
    _integer(config.index_data_in, "IndexDataIn", 0, 7999)
    if config.kind == "WRITE_READ_VAR":
        if config.obj_type != 0:
            fail("WRITE_READ_VAR supports memory words only")
        _integer(config.quantity, "WriteQuantity", 1, 121)
        _span(config.first_read_obj, config.read_quantity, 65536, "remote read range")
        _span(config.index_data_in, config.read_quantity, 8000, "local read buffer")
    else:
        if (config.first_read_obj, config.read_quantity, config.index_data_in) != (
            0,
            1,
            0,
        ):
            fail("read/write-only Modbus fields on a single-direction block")
        allowed = READ_FUNCTIONS if config.kind == "READ_VAR" else WRITE_FUNCTIONS
        if config.obj_type not in allowed:
            fail("unsupported Modbus ObjType for " + config.kind)
        if config.function_code not in (5, 6):
            maximum = (
                (2000 if config.obj_type in (1, 2) else 125)
                if config.kind == "READ_VAR"
                else (1968 if config.obj_type == 2 else 123)
            )
            _integer(config.quantity, "Quantity", 1, maximum)
    count = 1 if config.function_code in (5, 6) else config.quantity
    _span(config.first_obj, count, 65536, "remote object range")
    _span(config.index_data, config.data_words, 8000, "local data buffer")
    return config


class ModbusProtocolError(ValueError):
    """Incorrect response: CommError=0, OperError=2 (manual p174)."""

    comm_error = 0
    oper_error = 2


class ModbusExceptionResponse(ModbusProtocolError):
    comm_error = 254

    def __init__(self, code):
        self.oper_error = code
        super().__init__("Modbus exception " + str(code))


def _words(words, index, count):
    if len(words) < index + count:
        fail("Modbus local word buffer is too small")
    result = []
    for value in words[index : index + count]:
        _integer(value, "memory word bit pattern", -32768, 65535)
        result.append(value & 65535)
    return result


def encode_request(config, words=()):
    """Build one Modbus PDU. No I/O or mutation is performed."""
    validate_config(config)
    fc = config.function_code
    if config.kind == "READ_VAR":
        return struct.pack(">BHH", fc, config.first_obj, config.quantity)
    source = _words(words, config.index_data, config.data_words)
    if fc == 5:
        return struct.pack(">BHH", fc, config.first_obj, 0xFF00 if source[0] & 1 else 0)
    if fc == 6:
        return struct.pack(">BHH", fc, config.first_obj, source[0])
    if fc == 15:
        # Bit order inside both the local words and wire bytes is LSB-first.
        value = sum(word << (16 * i) for i, word in enumerate(source))
        value &= (1 << config.quantity) - 1
        data = value.to_bytes((config.quantity + 7) // 8, "little")
    else:
        data = struct.pack(">" + "H" * len(source), *source)
    if fc == 23:
        return (
            struct.pack(
                ">BHHHHB",
                fc,
                config.first_read_obj,
                config.read_quantity,
                config.first_obj,
                config.quantity,
                len(data),
            )
            + data
        )
    return struct.pack(">BHHB", fc, config.first_obj, config.quantity, len(data)) + data


def decode_response(config, request_pdu, response_pdu):
    """Validate a complete response before returning unsigned local word values."""
    validate_config(config)
    if not isinstance(response_pdu, bytes) or not isinstance(request_pdu, bytes):
        raise ModbusProtocolError("Modbus PDU must be bytes")
    fc = config.function_code
    if not request_pdu or request_pdu[0] != fc or not response_pdu:
        raise ModbusProtocolError("missing or incorrect Modbus function")
    if response_pdu[0] == fc | 0x80:
        if len(response_pdu) != 2 or response_pdu[1] not in EXCEPTION_CODES:
            raise ModbusProtocolError("invalid Modbus exception response")
        raise ModbusExceptionResponse(response_pdu[1])
    if response_pdu[0] != fc:
        raise ModbusProtocolError("incorrect Modbus response function")
    if fc in (5, 6, 15, 16):
        if len(response_pdu) != 5 or response_pdu != request_pdu[:5]:
            raise ModbusProtocolError("Modbus write response does not echo the request")
        return ()
    quantity = config.read_quantity if fc == 23 else config.quantity
    bits = fc in (1, 2)
    byte_count = (quantity + 7) // 8 if bits else quantity * 2
    if len(response_pdu) != byte_count + 2 or response_pdu[1] != byte_count:
        raise ModbusProtocolError("incorrect Modbus response length or byte count")
    data = response_pdu[2:]
    if bits:
        if quantity % 8 and data[-1] >> (quantity % 8):
            raise ModbusProtocolError("nonzero unused Modbus response bits")
        value = int.from_bytes(data, "little") & ((1 << quantity) - 1)
        return tuple((value >> (16 * i)) & 65535 for i in range((quantity + 15) // 16))
    return struct.unpack(">" + "H" * quantity, data)


def encode_tcp(transaction_id, unit_id, pdu):
    """Build an MBAP ADU; the Ethernet config Id is not passed as unit_id."""
    _integer(transaction_id, "TCP transaction Id", 0, 65535)
    _integer(unit_id, "TCP unit Id", 0, 255)
    if not isinstance(pdu, bytes) or not 1 <= len(pdu) <= 253:
        raise ModbusProtocolError("invalid Modbus TCP PDU length")
    return struct.pack(">HHHB", transaction_id, 0, len(pdu) + 1, unit_id) + pdu


def decode_tcp(frame, *, transaction_id, unit_id):
    """Accept exactly one ADU, including exact transaction and unit identity."""
    _integer(transaction_id, "expected TCP transaction Id", 0, 65535)
    _integer(unit_id, "expected TCP unit Id", 0, 255)
    if not isinstance(frame, bytes) or not 8 <= len(frame) <= 260:
        raise ModbusProtocolError("invalid Modbus TCP ADU length")
    transaction, protocol, length, unit = struct.unpack(">HHHB", frame[:7])
    if protocol != 0 or not 2 <= length <= 254 or len(frame) != length + 6:
        raise ModbusProtocolError("invalid Modbus TCP protocol or length")
    if transaction != transaction_id or unit != unit_id:
        raise ModbusProtocolError("unexpected Modbus TCP transaction or unit")
    return frame[7:]


@dataclass(frozen=True)
class CommunicationStatus:
    done: bool = False
    busy: bool = False
    aborted: bool = False
    error: bool = False
    comm_error: int = 0
    oper_error: int = 0


class ModbusTransportError(ValueError):
    """A transport reports documented numeric codes, without retrying implicitly."""

    def __init__(self, message, comm_error=255, oper_error=6):
        self.comm_error = comm_error
        self.oper_error = oper_error
        super().__init__(message)


class _BroadcastComplete:
    pass


# A transport must explicitly acknowledge sending a serial broadcast, which has
# no slave reply. None means still pending, never successful transmission.
BROADCAST_COMPLETE = _BroadcastComplete()


@dataclass
class _Execution:
    status: CommunicationStatus = CommunicationStatus()
    last_execute: object = None
    last_abort: object = None
    config: object = None
    request: bytes = b""
    token: object = None
    started_ms: int = 0
    destination: object = None


class CommunicationEngine:
    """Scan-driven local communication model with one active exchange per link.

    The injected transport implements start(config,pdu,now_ms)->token,
    poll(token,now_ms)->bytes|None|BROADCAST_COMPLETE and cancel(token).
    A missing transport yields Refused/ChannelNotConfigured (255/15).
    Simultaneous Abort wins over Execute and an occupied link yields
    Refused/SystemResourceMissing (255/11): conservative local policies, not
    claims about undocumented PLC scheduling. No automatic retry or queue.
    Each key must be updated once per simulated FB invocation; status() is pure.
    """

    def __init__(self, transport=None):
        self.transport = transport
        self._states = {}
        self._active_links = {}
        self._now_ms = 0
        self._properties = {}
        self._definitions = {}
        self._property_writes = {}

    def define(self, key, config):
        validate_config(config)
        previous = self._definitions.get(key)
        self._definitions[key] = config
        if key not in self._properties:
            self._properties[key] = initial_properties(config)
        values = self._properties[key]
        if previous is not None and previous != config:
            # Keep the historical direct-engine API: supplying a new immutable
            # config updates defaults, while explicit native-property stores win.
            for field, value in initial_properties(config).items():
                if field not in self._property_writes.get(key, ()):
                    values[field] = value

    def read_property(self, key, field):
        if key not in self._definitions or field not in DOMAINS[self._definitions[key].kind]:
            fail("undefined communication property")
        if key not in self._properties:
            self._properties[key] = initial_properties(self._definitions[key])
        return signed_word(self._properties[key][field])

    def write_property(self, key, field, value):
        self.read_property(key, field)
        _integer(value, "property word pattern", -32768, 65535)
        self._properties[key][field] = value & 65535
        self._property_writes.setdefault(key, set()).add(field)

    def lifecycle(self, event):
        """Explicit local lifecycle, separate from the VM's scan scheduler.

        Cold restores configured properties; warm preserves them. STOP cancels
        active tokens. Edge history is re-armed so first TRUE after RUN does not
        silently become an Execute rising edge. Exact controller resumption is
        still an official runtime acceptance case.
        """
        if event not in ("cold", "warm", "stop"):
            fail("unknown communication lifecycle event")
        if event == "warm":
            return
        for key, state in self._states.items():
            if state.status.busy:
                self._release(key, state, cancel=True)
            state.status = CommunicationStatus()
            state.last_execute = state.last_abort = None
        if event == "cold":
            self._properties = {key: initial_properties(cfg) for key, cfg in self._definitions.items()}
            self._property_writes.clear()

    def status(self, key):
        state = self._states.get(key)
        return state.status if state is not None else CommunicationStatus()

    def _release(self, key, state, cancel=False):
        if cancel and self.transport is not None:
            self.transport.cancel(state.token)
        if (
            state.config is not None
            and self._active_links.get(state.config.link) == key
        ):
            del self._active_links[state.config.link]
        state.token = None
        state.destination = None

    def update(self, key, config, execute, abort, now_ms, words):
        self.define(key, config)
        if type(execute) is not bool or type(abort) is not bool:
            fail("Modbus Execute and Abort inputs must be BOOL")
        _integer(now_ms, "monotonic clock (milliseconds)", self._now_ms)
        self._now_ms = now_ms
        if not isinstance(words, list):
            fail("Modbus requires the mutable shared MW word table")
        state = self._states.get(key)
        if state is not None and state.status.busy:
            current = state.config
        elif (state is not None and state.last_execute is False and execute
              and not (state.last_abort is False and abort)):
            try:
                current = effective_config(config, self._properties[key])
            except CompileError:
                # Individual stores may temporarily form an invalid parameter
                # set. Only an actual Execute snapshots/validates that set.
                state.last_execute, state.last_abort = execute, abort
                state.status = CommunicationStatus(error=True, comm_error=6)
                return state.status
        else:
            current = config
        return self._update(key, current, execute, abort, now_ms, words)

    def _update(self, key, config, execute, abort, now_ms, words):
        validate_config(config)
        if type(execute) is not bool or type(abort) is not bool:
            fail("Modbus Execute and Abort inputs must be BOOL")
        _integer(now_ms, "monotonic clock (milliseconds)", self._now_ms)
        self._now_ms = now_ms
        if not isinstance(words, list):
            fail("Modbus requires the mutable shared MW word table")
        state = self._states.setdefault(key, _Execution())
        execute_edge = state.last_execute is False and execute
        abort_edge = state.last_abort is False and abort
        state.last_execute, state.last_abort = execute, abort

        # A terminal result after Execute was already FALSE is visible for one
        # update, then cleared at the next invocation (timing diagrams p205).
        if not state.status.busy and not execute:
            state.status = CommunicationStatus()
        if state.status.busy:
            active = state.config
            if abort_edge:
                self._release(key, state, cancel=True)
                state.status = CommunicationStatus(aborted=True, comm_error=2)
            elif (
                active.timeout_100ms
                and now_ms - state.started_ms >= active.timeout_100ms * 100
            ):
                self._release(key, state, cancel=True)
                state.status = CommunicationStatus(error=True, comm_error=1)
            else:
                try:
                    response = self.transport.poll(state.token, now_ms)
                    if response is None:
                        return state.status
                    broadcast = active.link == "SL1" and active.id == 0
                    if broadcast:
                        if response is not BROADCAST_COMPLETE:
                            raise ModbusProtocolError(
                                "serial broadcast must not produce a slave response"
                            )
                        result = ()
                    else:
                        if response is BROADCAST_COMPLETE:
                            raise ModbusProtocolError(
                                "unicast transport did not return a response"
                            )
                        result = decode_response(active, state.request, response)
                    if result:
                        index = (
                            active.index_data_in
                            if active.kind == "WRITE_READ_VAR"
                            else active.index_data
                        )
                        state.destination[index : index + len(result)] = result
                    self._release(key, state)
                    state.status = CommunicationStatus(done=True)
                except (ModbusProtocolError, ModbusTransportError) as error:
                    self._release(key, state, cancel=True)
                    state.status = CommunicationStatus(
                        error=True,
                        comm_error=error.comm_error,
                        oper_error=error.oper_error,
                    )
            # Execute edges during an exchange never schedule a second one.
            return state.status

        if execute_edge and not abort_edge:
            if config.link in self._active_links:
                state.status = CommunicationStatus(
                    error=True, comm_error=255, oper_error=11
                )
            elif self.transport is None:
                state.status = CommunicationStatus(
                    error=True, comm_error=255, oper_error=15
                )
            else:
                output_count = (
                    config.read_quantity
                    if config.kind == "WRITE_READ_VAR"
                    else config.data_words
                )
                output_index = (
                    config.index_data_in
                    if config.kind == "WRITE_READ_VAR"
                    else config.index_data
                )
                if (
                    config.kind != "WRITE_VAR"
                    and len(words) < output_index + output_count
                ):
                    fail("Modbus local response buffer is too small")
                request = encode_request(config, words)
                try:
                    token = self.transport.start(config, request, now_ms)
                except (ModbusProtocolError, ModbusTransportError) as error:
                    state.status = CommunicationStatus(
                        error=True,
                        comm_error=error.comm_error,
                        oper_error=error.oper_error,
                    )
                else:
                    state.config, state.request = config, request
                    state.token, state.started_ms = token, now_ms
                    state.destination = words
                    self._active_links[config.link] = key
                    state.status = CommunicationStatus(busy=True)
        return state.status


class MemoryModbusPeer:
    """Explicit deterministic local peer with separate Modbus data spaces.

    It is a protocol reference model, not a PLC emulator. Tables can be shorter
    than 65536 entries to model unimplemented remote addresses. Writes validate
    both sides of FC23 before mutating anything; FC23 writes before reading.
    """

    def __init__(
        self,
        *,
        holding_registers=None,
        input_registers=None,
        coils=None,
        discrete_inputs=None,
    ):
        for name, data, bits in (
            ("holding_registers", holding_registers, False),
            ("input_registers", input_registers, False),
            ("coils", coils, True),
            ("discrete_inputs", discrete_inputs, True),
        ):
            data = ([False if bits else 0] * 65536) if data is None else list(data)
            if len(data) > 65536:
                fail("Modbus peer table exceeds address space")
            if bits:
                if any(type(value) is not bool for value in data):
                    fail("Modbus peer bit table requires BOOL values")
            else:
                for value in data:
                    _integer(value, "peer register", 0, 65535)
            setattr(self, name, data)

    def handle_request(self, pdu):
        if not isinstance(pdu, bytes) or not pdu:
            raise ModbusProtocolError("empty Modbus peer request")
        fc = pdu[0]

        def exception(code):
            return bytes([fc | 128, code])

        def address_ok(table, first, quantity):
            return first + quantity <= len(table)

        if fc in (1, 2, 3, 4):
            if len(pdu) != 5:
                return exception(3)
            first, quantity = struct.unpack(">HH", pdu[1:])
            bits = fc in (1, 2)
            if not 1 <= quantity <= (2000 if bits else 125):
                return exception(3)
            table = {
                1: self.coils,
                2: self.discrete_inputs,
                3: self.holding_registers,
                4: self.input_registers,
            }[fc]
            if not address_ok(table, first, quantity):
                return exception(2)
            values = table[first : first + quantity]
            if bits:
                data = sum(int(bit) << i for i, bit in enumerate(values)).to_bytes(
                    (quantity + 7) // 8, "little"
                )
            else:
                data = struct.pack(">" + "H" * quantity, *values)
            return bytes([fc, len(data)]) + data
        if fc in (5, 6):
            if len(pdu) != 5:
                return exception(3)
            first, value = struct.unpack(">HH", pdu[1:])
            if fc == 5 and value not in (0, 0xFF00):
                return exception(3)
            table = self.coils if fc == 5 else self.holding_registers
            if not address_ok(table, first, 1):
                return exception(2)
            table[first] = bool(value) if fc == 5 else value
            return pdu
        if fc in (15, 16, 23):
            header_size = 10 if fc == 23 else 6
            if len(pdu) < header_size:
                return exception(3)
            if fc == 23:
                read_first, read_quantity, first, quantity, byte_count = struct.unpack(
                    ">HHHHB", pdu[1:10]
                )
                if not 1 <= read_quantity <= 125:
                    return exception(3)
            else:
                first, quantity, byte_count = struct.unpack(">HHB", pdu[1:6])
            maximum = 1968 if fc == 15 else (121 if fc == 23 else 123)
            expected = (quantity + 7) // 8 if fc == 15 else quantity * 2
            if (
                not 1 <= quantity <= maximum
                or byte_count != expected
                or len(pdu) != header_size + byte_count
            ):
                return exception(3)
            table = self.coils if fc == 15 else self.holding_registers
            if not address_ok(table, first, quantity):
                return exception(2)
            if fc == 23 and not address_ok(table, read_first, read_quantity):
                return exception(2)
            data = pdu[header_size:]
            if fc == 15:
                if quantity % 8 and data[-1] >> (quantity % 8):
                    return exception(3)
                value = int.from_bytes(data, "little")
                values = [bool(value & (1 << i)) for i in range(quantity)]
            else:
                values = list(struct.unpack(">" + "H" * quantity, data))
            table[first : first + quantity] = values
            if fc == 23:
                return bytes([fc, read_quantity * 2]) + struct.pack(
                    ">" + "H" * read_quantity,
                    *table[read_first : read_first + read_quantity],
                )
            return pdu[:5]
        return exception(1)


class MemoryTransport:
    """Explicit local peer transport; no sockets or serial I/O.

    A single peer answers injected requests independently of address routing.
    At most two pending exchanges are retained (the two modeled links), with
    no retries. Local broadcast completion means the peer processed the write.
    """

    def __init__(self, peer, latency_ms=1):
        if not isinstance(peer, MemoryModbusPeer):
            fail("MemoryTransport requires an explicit local Modbus peer")
        _integer(latency_ms, "local peer latency (milliseconds)", 0)
        self.peer = peer
        self.latency_ms = latency_ms
        self._pending = {}
        self._next_token = 0

    def start(self, config, pdu, now_ms):
        validate_config(config)
        _integer(now_ms, "local transport clock", 0)
        if not isinstance(pdu, bytes) or not 1 <= len(pdu) <= 253:
            raise ModbusProtocolError("invalid local Modbus request PDU length")
        if len(self._pending) >= 2:
            raise ModbusTransportError("local transport capacity exceeded", 255, 11)
        self._next_token += 1
        self._pending[self._next_token] = (config, bytes(pdu), now_ms + self.latency_ms)
        return self._next_token

    def poll(self, token, now_ms):
        if token not in self._pending:
            raise ModbusTransportError("local exchange is no longer active", 255, 12)
        config, pdu, ready_ms = self._pending[token]
        if now_ms < ready_ms:
            return None
        del self._pending[token]
        response = self.peer.handle_request(pdu)
        if config.link == "SL1" and config.id == 0:
            # A malformed broadcast must not be presented as successful.
            if response[0] & 128:
                raise ModbusExceptionResponse(response[1])
            return BROADCAST_COMPLETE
        return response

    def cancel(self, token):
        self._pending.pop(token, None)


@dataclass
class _TCPExchange:
    connection: object
    transaction: int
    request: bytes
    connected: bool = False
    sent: int = 0
    response: bytes = b""
    unmatched_responses: int = 0


class LoopbackTCPTransport:
    """Explicit nonblocking TCP reference client restricted to IPv4 loopback.

    No connection is made at construction. One exchange is allowed at a time,
    with no retries, no DNS, a 260-byte receive bound, and a fresh connection per
    exchange. At most 16 complete responses for other transaction IDs are
    discarded; the next one fails closed, including when timeout is disabled.
    remote_index selects one configured ETH1 Id; unit_id is separate.
    Physical Ethernet/serial operation is deliberately outside this local tool.
    CommunicationEngine supplies the scan clock, timeout, and cancellation.
    """

    def __init__(self, *, port, host="127.0.0.1", unit_id=1, remote_index=1):
        try:
            address = ipaddress.ip_address(host)
        except (ValueError, TypeError):
            fail("local Modbus TCP transport requires a numeric IPv4 loopback address")
        if not isinstance(address, ipaddress.IPv4Address) or not address.is_loopback:
            fail("Modbus TCP reference transport is restricted to IPv4 loopback")
        _integer(port, "local TCP port", 1, 65535)
        _integer(unit_id, "TCP unit Id", 0, 255)
        _integer(remote_index, "Ethernet remote-server index", 1, 16)
        self.host, self.port = str(address), port
        self.unit_id, self.remote_index = unit_id, remote_index
        self._pending = {}
        self._next_token = 0

    def start(self, config, pdu, now_ms):
        validate_config(config)
        if config.link != "ETH1" or config.id != self.remote_index:
            raise ModbusTransportError(
                "local TCP remote-server index is not configured", 255, 15
            )
        if self._pending:
            raise ModbusTransportError(
                "local TCP transport already has an active exchange", 255, 11
            )
        self._next_token += 1
        transaction = self._next_token & 65535
        frame = encode_tcp(transaction, self.unit_id, pdu)
        connection = None
        try:
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection.setblocking(False)
            result = connection.connect_ex((self.host, self.port))
            if result not in (
                0,
                errno.EINPROGRESS,
                errno.EALREADY,
                errno.EWOULDBLOCK,
                errno.EINTR,
            ):
                raise OSError(result, "local Modbus TCP connection failed")
            self._pending[self._next_token] = _TCPExchange(
                connection, transaction, frame, connected=result == 0
            )
        except OSError as error:
            if connection is not None:
                connection.close()
            raise ModbusTransportError(
                "local Modbus TCP connection failed: " + str(error)
            ) from error
        return self._next_token

    def poll(self, token, now_ms):
        exchange = self._pending.get(token)
        if exchange is None:
            raise ModbusTransportError(
                "local TCP exchange is no longer active", 255, 12
            )
        connection = exchange.connection
        try:
            if not exchange.connected:
                _, writable, exceptional = select.select(
                    [], [connection], [connection], 0
                )
                if not writable and not exceptional:
                    return None
                error = connection.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if error:
                    raise OSError(error, "local Modbus TCP connection failed")
                exchange.connected = True
            if exchange.sent < len(exchange.request):
                try:
                    sent = connection.send(exchange.request[exchange.sent :])
                except BlockingIOError:
                    return None
                if sent == 0:
                    raise OSError("local Modbus TCP request could not be sent")
                exchange.sent += sent
                if exchange.sent < len(exchange.request):
                    return None
            target_size = 7
            if len(exchange.response) >= 7:
                _, protocol, length, _ = struct.unpack(">HHHB", exchange.response[:7])
                if protocol != 0 or not 2 <= length <= 254:
                    raise ModbusProtocolError(
                        "incorrect Modbus TCP header or response length"
                    )
                target_size = length + 6
            try:
                # Read only the current ADU. TCP may combine an unrelated
                # response and the pending response in one socket write.
                part = connection.recv(target_size - len(exchange.response))
            except BlockingIOError:
                return None
            if not part:
                if exchange.response:
                    raise ModbusProtocolError("truncated Modbus TCP response")
                raise OSError("local Modbus TCP peer closed without a response")
            exchange.response += part
            if len(exchange.response) < 7:
                return None
            transaction, protocol, length, unit = struct.unpack(
                ">HHHB", exchange.response[:7]
            )
            if (
                protocol != 0
                or not 2 <= length <= 254
                or len(exchange.response) > length + 6
            ):
                raise ModbusProtocolError(
                    "incorrect Modbus TCP header or response length"
                )
            if len(exchange.response) < length + 6:
                return None
            if transaction != exchange.transaction:
                # TCP Implementation Guide V1.0b 4.4.1.3: an unmatched TID
                # has no pending request and must not complete or fail it.
                exchange.unmatched_responses += 1
                if exchange.unmatched_responses > 16:
                    raise ModbusProtocolError("too many unmatched Modbus TCP responses")
                exchange.response = b""
                return None
            if unit != self.unit_id:
                raise ModbusProtocolError("incorrect Modbus TCP unit identifier")
            response = decode_tcp(
                exchange.response,
                transaction_id=exchange.transaction,
                unit_id=self.unit_id,
            )
            self.cancel(token)
            return response
        except OSError as error:
            self.cancel(token)
            raise ModbusTransportError(
                "local Modbus TCP channel error: " + str(error)
            ) from error
        except ModbusProtocolError:
            self.cancel(token)
            raise

    def cancel(self, token):
        exchange = self._pending.pop(token, None)
        if exchange is not None:
            exchange.connection.close()

    def close(self):
        """Release all connections owned by this transport."""
        for token in tuple(self._pending):
            self.cancel(token)
