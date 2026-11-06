# Modbus — TM200CE40T parity audit

Audit date: 2026-11-06. The compiler implements a useful communication subset, but **Modbus parity with the official profile is incomplete**. SDK/IL, protocol and local transports exist; SMBP export is narrower, and local tests do not establish official runtime or physical behavior.

The initial audit inspected source, existing tests, local manuals and installed editor metadata without executing tests or probing devices. The subsequent focused transport change and its local verification are recorded in [MODBUS-TRANSPORT-LOCAL-RESULTS.md](../validation/MODBUS-TRANSPORT-LOCAL-RESULTS.md). Neither stage operated the official editor/simulator, Wine, external Modbus endpoints, physical serial links or PLCs.

## Sources and evidence strength

| Source | Evidence used |
|---|---|
| [Programming Guide EIO0000002019.06](https://www.se.com/ww/en/download/document/EIO0000002019/) | Local M100/M200 manual, especially pp.25, 111–136, 215–221, 331–332. SHA256 `fb4f684e7efbb46e3e38e61ed532d99bf623bedffe447b5c379dd3dd6c4434df`, verified during this audit. |
| [Generic Functions Library EIO0000003289.04](https://www.se.com/ww/en/download/document/EIO0000003289/) | FB contracts, parameters, errors and timing, pp.171–192 and 204–205. SHA256 `d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595`, verified. |
| [Operating Guide EIO0000003281.04](https://www.se.com/ww/en/download/document/EIO0000003281/) | Memory allocation, pp.47–48. SHA256 `2fb60e335bbe92342760471777abf256da7a434c61b98b464ae234aaa82c45e5`, verified. |
| Installed Machine Expert Basic 1.4 build484 | Metadata from `SchneiderElectric.SoMachineBasic.Entities.dll`, SHA256 `bf7b33a79356dbfd9839891b00e61695b5af3b5ee7ce121def37e3e973a9455e`, verified. Identifiers/enums prove existence and names, not complete serialization or execution. |
| [Format research](MODBUS-FORMAT-RESEARCH.md) | Preserved third-party projects identified by hash/commit. They establish observed fields and graphics while retaining their original CE40R/M221 CPUs. |
| [Implementation](../../m200/modbus.py), [XML](../../m200/communication_xml.py), [SDK](../../sdk/plc.hpp), tests and lab notes | Establish local contracts and explicitly recorded history; they do not replace official runtime evidence. |

PDFs and extracted text are under `research/downloads/manuals`. Values were checked against those files rather than relying on older summaries. Protocol references used by the implementation are [Modbus Application Protocol V1.1b3](https://www.modbus.org/file/secure/modbusprotocolspecification.pdf) and [Modbus TCP Implementation Guide V1.0b](https://www.modbus.org/file/secure/messagingimplementationguide.pdf).

## Implemented coverage

| Layer | Implemented | Current limit |
|---|---|---|
| C++/frontend | `ReadVar`, `WriteVar`, `WriteReadVar`; literal/enum configuration; automatic or explicit indices; `update(execute, abort)` and Done/Busy/Aborted/Error/CommError/OperError getters. | One unconditional update per scan; automatic and explicit indices cannot be mixed within one kind. Indices 0..31, with a project functional-level gate. No setters for dynamic FB properties. |
| IL/VM/reverse | Native READ_VAR/WRITE_VAR/WRITE_READ_VAR blocks, Execute/Abort, status reads at their original scan position; reconstruction of sparse indices and buffers. | Closed IL forms; unknown properties/configurations are rejected. This is not a universal Schneider runtime interpreter. |
| Local protocol | FC1/2/3/4/5/6/15/16/23, responses/echoes/exceptions, packed bits, MBAP and complete buffer bounds. | No FC8 diagnostics or FC43/14 identification; does not implement complete TM200 server semantics. |
| Local states | Execute edge; TRUE on the first scan does not trigger; Busy, terminal results, timeout, Abort, cancellation cleanup and one active exchange per link. | Simultaneous Abort/Execute priority, occupied-link refusal and some numeric resets are conservative local policies without physical PLC differential evidence. No automatic queue/retry. |
| Memory transport | `MemoryModbusPeer` with separate coils, discrete inputs, holding/input registers; `MemoryTransport` with latency and at most two pending exchanges. | No sockets, CRC or actual device routing. Local broadcast processing does not prove RS485 transmission. |
| VM TCP transport | `LoopbackTCPTransport`: numeric IPv4 loopback, explicit Unit ID, nonblocking I/O, fragmented/coalesced ADU framing, timeout/cancellation through the engine. Unmatched transaction responses are discarded. | No DNS or physical network. One pending exchange and a fresh connection per exchange; at most 260 buffered bytes and one receive per poll. Up to 16 unmatched complete ADUs are discarded; the seventeenth fails closed. Endpoint configuration is explicit and separate from SMBP. |
| Native C++ execution | Test transport callback `plc::detail::communication_hook`; without a callback, an execution edge returns error 255/15. | The SDK contains no physical TCP/serial client or full duplicate of the Python asynchronous engine. The callback supplies states; declaring an FB does not perform communication. |
| XML/SMBP | READ_VAR with MW/IW; WRITE_VAR with MW; exact .NET wrappers; established SL1 settings or an ETH1 RemoteServer; candidate reimport and preservation of the previous destination. | Bits, single writes, WRITE_READ_VAR, graphical ABORT and other layouts remain blocked. Those tests do not demonstrate editor acceptance or actual communication execution. |
| Network configuration | Preserves/validates observed RS485/RTU and Ethernet remote subsets. Rejects active IOScanner, Modbus mapping and EtherNet/IP assemblies. | No complete authoring of those services. A preserved Ethernet field or parser-accepted profile does not prove that a runtime service is enabled or reachable. |

Main sources: [frontend](../../m200/frontend.py), [communication forms](../../m200/communication.py), [VM](../../m200/il.py), [configuration](../../m200/config.py), [Ladder/SMBP](../../m200/project.py) and [reverse](../../m200/reverse.py).

### Operations, addresses and local limits

| API/object | Function | Maximum quantity per exchange |
|---|---:|---:|
| ReadVar / Coils, DiscreteInputs | 1, 2 | 2000 bits |
| ReadVar / HoldingWords, InputWords | 3, 4 | 125 words |
| WriteVar / SingleCoil, SingleRegister | 5, 6 | 1; Quantity does not determine the length |
| WriteVar / Coils, HoldingWords | 15, 16 | 1968 bits / 123 words |
| WriteReadVar / HoldingWords | 23 (`0x17`) | 121 write words + 125 read words |

Validation checks the entire remote range within 0..65535 and the entire local buffer within the 8000 words shared by MW/MD/MF. Bits start at bit0; register bytes use big-endian order, without inferring another manufacturer's two-word order for 32-bit values. Timeout is in 100ms units; zero does not expire. The ceiling `2147483647` is an Int32/SDK representation bound, not a proven physical controller timeout limit.

SL1 uses IDs 1..247; ID0 is allowed only for WRITE_VAR broadcast. ETH1 uses remote index 1..16, which **is not the MBAP Unit ID**. Observed XML associates FB ID1 with `RemoteServer/DeviceId=0`. `ChannelUnitId` and `InitRequestUnitId` are separate fields. `SlavePort` is the local server port; the implementation does not turn it into a remote port. Current authoring assumes remote port 502 in the established format; the test transport uses its own explicit port.

The TCP transport accepts numeric addresses recognized by `IPv4Address.is_loopback`, not only the literal string `127.0.0.1`. Construction opens no connection. An unrelated transaction cannot complete the active request or change memory; a malformed response for the active transaction is rejected. Cancelled exchanges are not reused. These checks do not provide device authentication or encryption.

### Currently accepted native configuration

- An active SL1 FB requires explicit `MasterAddressing`, RS485, RTU, baud, parity, data bits, stop bits and response time. The serial allowlist covers 9600/19200, Even/None, 8 bits, 1 stop bit and No Modem. This is a tool/evidence limit, not the port's complete capability range.
- ETH1 requires a matching remote, the observed Generic Device shape and a numeric unicast IPv4 address. The exporter does not invent a device, address, protocol or security-service enablement.
- Capacity is 16 instances per kind below functional level 10.1 and 32 from 10.1. [levels.py](../../m200/levels.py) resolves internal tokens: `FunctLevelMan14_0` means 10.0; `FunctLevelMan15_0`, 10.1; `FunctLevelMan18_0`, 12.0. Unknown tokens fail. The historical closing note in `MODBUS-FORMAT-RESEARCH.md` that treated suffix 18 as level 18.0 is superseded by installed evidence and current implementation.
- An authentic CE40T baseline now exists in the editor work. This does not retrospectively establish a CE40T project with every Modbus channel configured: historical serialization examples retain their original CPUs.

## Documented capabilities beyond the implementation

The M200 profile documents Ethernet client/server and embedded SL1, plus cartridge port options subject to model and functional level. Its manual lists 8 server connections and 1 TCP client: 16 configured remotes do not imply 16 simultaneous clients. SL1 supports more baud/mode choices than the current allowlist. [Programming Guide, pp.25, 75, 111–128](https://www.se.com/ww/en/download/document/EIO0000002019/).

The documented serial server supports FC1/2 on `%M`, FC3/4 on `%MW`, FC5/6/15/16/23, FC8 subfunctions 0 and 10..18, and FC43/14. These internal spaces must not be confused with physical `%I`/`%Q` or the test peer's four independent spaces. TCP mapping has its own `%IWM/%QWM`, Unit ID and rules; active mapping is currently rejected by the parser. [Programming Guide, pp.117–118, 134–136, 215–216](https://www.se.com/ww/en/download/document/EIO0000002019/).

IOScanner is a separate service: serial or Ethernet, one global instance, up to 16 devices, 20 initializations/device and 10 channels/device. Its per-channel bit limit is 128, unlike READ_VAR/WRITE_VAR's 2000/1968. Its states, initialization, cycles, triggers and failure policy are not modeled. [Programming Guide, pp.116–136](https://www.se.com/ww/en/download/document/EIO0000002019/).

Official FBs allow runtime-writable properties, port sharing with EXCH, and additional blocks such as SEND_RECV_MSG. The tool does not yet cover that surface. WRITE_VAR FC5/6 require functional level ≥5.0; that is not a general gate for all reads. [Generic Functions Library, pp.171–192](https://www.se.com/ww/en/download/document/EIO0000003289/).

EtherNet/IP is a separate protocol. Hardware research records the advertised adapter with incomplete configuration evidence; there is no basis to classify it as impossible on CE40T or as implemented by the compiler. See [HARDWARE-AUDIT.md](HARDWARE-AUDIT.md).

### Installed metadata narrows a knowledge gap

The installed Entities enum `SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks.Enums.FBComObjTypeParameterEnums` contains `MW=0`, `I=1`, `Q=2`, `IW=3`, `SINGLE_COIL=4`, `SINGLE_REG=5` (TypeDef541). `FBComLinkParameterEnums` contains `SerialLine1=1`, `SerialLine2=2`, `EthernetLink=3`, `SerialLine3=4` (TypeDef542).

Classes `ReadVarBasic`, `WriteVarBasic`, `WriteReadVarBasic` and `SendRecvMsgBasic` also exist under namespace `.PLCObjects.FunctionBlocks.Com`. These provide official candidate names to investigate, not proof of every parameter wrapper, default, version, Ladder geometry or behavior. Export remains limited to MW/IW and the two established links. SDK numbers (`Serial1=1`, `Ethernet=2`) are not copies of vendor enum numbers; translation uses semantic names. SDK value 2 must not be emitted as XML `SerialLine2`.

## Existing tests and what they establish

The initial static inventory found **79 test methods** in the first four files below; six focused transport regressions were subsequently added. The historical run in [LOCAL-RESULTS.md](../validation/LOCAL-RESULTS.md) belongs to the revision and stage recorded there. The new 85-test focused run is documented separately.

| File | Methods | Coverage established by source inspection |
|---|---:|---|
| [test_modbus.py](../../tests/test_modbus.py) | 48 | Complete ranges, FCs/PDUs, bits/endianness, MBAP, exceptions, states/edges/timeout/Abort, occupied link, overlapping buffers, broadcast, memory peer, fragmented real loopback sockets, incorrect headers, silence, cancellation and socket resource exhaustion. |
| [test_communication_compiler.py](../../tests/test_communication_compiler.py) | 7 | C++ → IL, shared buffers, getters, sparse native indices, explicit errors, reverse and native equivalence without a transport. |
| [test_communication_xml.py](../../tests/test_communication_xml.py) | 17 | Wrappers/types/cardinality, rejection without mutation, configuration/IDs, functional-level gates using actual enums, Int32 bounds and explicit serial format. |
| [test_communication_project.py](../../tests/test_communication_project.py) | 7 | SMBP FB/Ladder candidates, reimport, destination preservation, status before update, buffers and generated-project integration with the VM's actual TCP loopback transport. |
| [test_modbus_transport_recovery.py](../../tests/test_modbus_transport_recovery.py) | 6 | Unmatched transactions before fragmented/coalesced replies, timeout and reconnect, bounded unmatched-frame floods, and recovery after wrong Unit ID, exception or truncated response. |

The TCP integration test uses a Python server on an ephemeral port and `Machine(..., communication_transport=LoopbackTCPTransport(...))`. It does **not** execute the project in M2xxBasicSIM, the official runtime or the PLC. The project implements its own peer; it does not replace interoperability with an independent device. XML tests use controlled builders and identified format sources; they do not turn foreign CPU profiles into CE40T evidence.

## Official simulator and external guard status

The lab records an earlier external read attempt on `127.0.0.1:502` with timeout and an AccessViolation in `getsockopt` inside `ModbusTcpServerTask`. The project had Ethernet protocols disabled. That incident therefore does not validate the server, independently establish Unit ID semantics or prove a defect in the VM's PDU implementation.

An independent investigation identified an invalid optlen argument in the executable and tested a user-owned guard in separate probes. **The guard remains outside the Schneider directory, with no override applied to the editor/simulator/launchers.** Its ephemeral-port loopback probe is not a real simulator Modbus test. A working internal editor connection also does not establish the external Modbus server.

Local source: `/Users/tommy/Offline/plc-mac-lab/STATUS.md`, particularly the external TCP record and `diagnostics/runtime-20261106/REPORT.txt`/`manifest.json`. This work did not apply the guard or access port 502. The separate `ProcessMbitsEdges → MastTask` sequence-loading crash before RUN is another incident and must not be grouped with `getsockopt` without evidence.

## Gaps and next tests, in useful order

| Priority | Concrete gap | Next verifiable result |
|---|---|---|
| 1 | Exported READ/WRITE word projects lack a complete official Modbus cycle. | Create explicit CE40T SL1 and ETH1 profiles in the editor; preserve bytes/hashes; open, validate, save/reopen and compare wrappers, configuration, Ladder and IL one read/write case at a time. Do not expect the local model to explain configuration it does not preserve. |
| 1 | The simulator's external server remains unvalidated; the guard is only a candidate. | In separate authorized runtime work, establish an unchanged control and guard candidate separately, correct service configuration and an initial read request. Record request/response capture, Unit ID, memory, timeout and process stability. A standalone socket probe does not complete this stage. |
| 2 | Enum names are known, but payload/graphics are unproved for bits, FC5/6, WRITE_READ_VAR and ABORT. | Obtain editor-created/saved CE40T projects for each case/pin; compare installed names with actual XML, import/reexport, then expand allowlists and positive/negative tests. Preserve destinations on rejection. |
| 2 | Dynamic LINK/ID/TIMEOUT/OBJTYPE/FIRSTOBJ/QUANTITY/INDEXDATA and EXCH contention lack API/parity. | Record official runtime behavior for effective configuration changes, buffers captured at Execute, edges during Busy, simultaneous Abort, link changes and error codes; derive a C++/IL/VM/reverse contract from those results. |
| 2 | Local protocol work does not establish RS485, physical scheduling or reliability. | In an explicitly authorized physical stage, compare an independent peer using RTU/CRC, address/broadcast, baud/parity, timeouts, exceptions, cancellation and recovery; repeat only cases yielding new evidence. |
| 3 | IOScanner, server mapping, diagnostics/identification and SEND_RECV_MSG/EXCH remain outside the subset. | Give each feature an official example, configuration, memory-object contract, failure/recovery behavior and Ladder/reverse backend. Do not reuse READ_VAR limits for IOScanner or a generic peer map for the TM200 server. |
| 3 | Optional ports, multiple remotes and remote ports other than 502 are unproved in the exporter. | Preserve official model/cartridge/level and configuration; separate remote index, Unit ID and port. An enum name does not authorize inventing hardware trees or a port field. |

These are future tasks, not actions performed or authorized by this document. Official validation and integrity checks remain necessary. This inventory provides no reason to remove gates or declare complete Modbus parity.


## Subsequent scoped implementation

A later closed binding increment adds READ_VAR I/Q and WRITE_VAR Q from exact CE40T official saves and fresh reopens. Packed MW buffer and direction checks remain enforced. Single writes, WRITE_READ_VAR and connected Abort/output graph forms remain gated in the product. The original audit table describes its earlier checkpoint; editor binding evidence still does not establish an actual exchange.
