# Modbus READ_VAR / WRITE_VAR: evidence and remaining gaps

Audit date: 2026-11-05. This is a read-only study of public authored SMBP projects and Schneider documentation. No project was opened, compiled or saved in Machine Expert Basic, and no PLC was connected. Serialization examples are evidence of observed fields, not an official schema or a guarantee that an emitted CE40T project is accepted.

## Sources and reproducibility

| ID | Primary source | Identity and role |
|---|---|---|
| G | [Generic Functions Library Guide EIO0000003289.04](https://www.se.com/ww/en/download/document/EIO0000003289/) | Local `research/downloads/manuals/EIO0000003289.pdf` / `.txt`; behavior pp.171-181, timing pp.204-205. PDF SHA256 freshly verified as `d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595`. |
| P | [M100/M200 Programming Guide EIO0000002019.06](https://www.se.com/ww/en/download/document/EIO0000002019/) | M200-specific capabilities, port existence and budgets; existing `HARDWARE-AUDIT.md` records p.25 instance budgets. Its old temporary source path was unavailable during this sub-audit, so that row is not fresh independent budget verification. |
| GP | [Mohammed-Helal/GP26 Ladder_Code.smbp](https://github.com/Mohammed-Helal/GP26/blob/0f68ca90f7fd51d44176b8bea01e73039c8e0641/Ladder_Code.smbp) | Commit `0f68ca90f7fd51d44176b8bea01e73039c8e0641`, blob `2bed3b7e2aecc47d28adf0ca3d5e8d941bfd9cac`. Original local file `research/downloads/public-projects/07-Ladder_Code.smbp`, SHA256 `fac44c53efcba56b5664d1cc59ce33d2fc230480a51351966066ed022b82eef7`. Project 2.7.0.0, `FunctLevelMan18_0`, actual controller **TM200CE40R**, HardwareId1966. Contains SL1 READ_VAR0 and WRITE_VAR0, MW. |
| WS | [wavestone-cdt/plc-code-security demo3.smbp](https://github.com/wavestone-cdt/plc-code-security/blob/a7fc4f9aa395ccbf628e888918fb6281995901b9/icsjwg2022/plc_programs/demo3.smbp) | Commit `a7fc4f9aa395ccbf628e888918fb6281995901b9`, blob `1125b00da5de770080e2c5cca05688c916824764`. Fetched through GitHub connector during this audit. Project2.2.0.0, `FunctLevelMan11_0`, actual controller **TM221ME16R/G**. Contains READ_VAR0 with Ethernet link and remote server configuration. Tool-returned UTF-8 text saved in `/tmp/m200-modbus-demo3.smbp`; line endings may differ from blob. |
| LP | [larottao/ModbusPollWannaBe Read Write values from TM221CE16R.smbp](https://github.com/larottao/ModbusPollWannaBe/blob/0f097a87c271e4f31d5b31aec26fd7d3ed33c3ea/Read%20Write%20values%20from%20TM221CE16R.smbp) | Commit `0f097a87c271e4f31d5b31aec26fd7d3ed33c3ea`, blob `b779bfa0ed102ebf22f4695ed59200ea71c38a49`. Fetched through GitHub connector. Additional actual `IW` object enum proof. Tool-returned text `/tmp/m200-modbus-larotta.smbp`. |

GP is an authored M200 project, but it is a relay model. Do not infer CE40T hardware IDs, input/output characteristics or complete CPU configuration from it. WS and LP support shared communication serialization patterns only. No authentic CE40T project was established by this audit.

## Typed function block serialization

The path is `ProjectDescriptor/SoftwareConfiguration/FunctionBlocks/IFunctionBlock`. Both GP instances use the following ordered children:

| Child | Serialized value path | Observed GP READ / WRITE |
|---|---|---|
| `Address` | text | `%READ_VAR0` / `%WRITE_VAR0` |
| `Index` | text integer | 0 / 0 |
| `Link` | `Value/FBComLinkParameterEnums` | `SerialLine1` / `SerialLine1` |
| `RemoteDeviceId` | `Value/int` | 1 / 1 |
| `Timeout` | `Value/int` | 100 / 100 |
| `ObjType` | `Value/FBComObjTypeParameterEnums` | `MW` / `MW` |
| `FirstObj` | `Value/int` | 0 / 1 |
| `Quantity` | `Value/int` | 1 / 1 |
| `IndexData` | `Value/int` | 100 / 1 |

GP lines2304-2381 provide complete attribute strings; these must not be replaced with a guessed simple Type name. The assembly suffix below is exact:

```text
SchneiderElectric.SoMachineBasic.Entities, Version=1.0.0.0, Culture=neutral, PublicKeyToken=5beddbc0114a5f07
```

`IFunctionBlock/@Type` uses either:

```text
SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks.Com.ReadVarBasic, SchneiderElectric.SoMachineBasic.Entities, Version=1.0.0.0, Culture=neutral, PublicKeyToken=5beddbc0114a5f07
SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks.Com.WriteVarBasic, SchneiderElectric.SoMachineBasic.Entities, Version=1.0.0.0, Culture=neutral, PublicKeyToken=5beddbc0114a5f07
```

Each integer parameter has this exact `Type` attribute:

```text
SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks.FbParameterElementRangeType`1[[System.Int32, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]], SchneiderElectric.SoMachineBasic.Entities, Version=1.0.0.0, Culture=neutral, PublicKeyToken=5beddbc0114a5f07
```

`Link/@Type` is:

```text
SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks.FbParameterElementEnumType`1[[SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks.Enums.FBComLinkParameterEnums, SchneiderElectric.SoMachineBasic.Entities, Version=1.0.0.0, Culture=neutral, PublicKeyToken=5beddbc0114a5f07]], SchneiderElectric.SoMachineBasic.Entities, Version=1.0.0.0, Culture=neutral, PublicKeyToken=5beddbc0114a5f07
```

`ObjType/@Type` has the same wrapper, using `FBComObjTypeParameterEnums` in place of `FBComLinkParameterEnums` in the generic argument. Its nested Value child also uses that enum type name.

Observed raw XML enums, without inference:

| Meaning | Raw XML value | Evidence |
|---|---|---|
| SL1 | `SerialLine1` | GP READ and WRITE; LP READ |
| Ethernet ETH1 | `EthernetLink` | WS READ_VAR0, lines2531-2570 |
| Holding registers / FC03 read, FC16 write | `MW` | GP, WS |
| Input registers / FC04 read | `IW` | LP READ_VAR0, aroundline2790 |

No authentic `SerialLine2`, bit-object enum spelling or single-coil/register enum spelling was established. The numeric object types in G do not prove XML enum names. Preserve unknown input XML or fail explicit authoring; never fabricate the spellings.

## Ladder and IL

GP has genuine graphical elements for both block types:

```xml
<LadderEntity>
  <ElementType>ReadVarBasic</ElementType>
  <Descriptor>%READ_VAR0</Descriptor>
  <Comment />
  <Symbol />
  <Row>0</Row>
  <Column>2</Column>
  <ChosenConnection>Left</ChosenConnection>
</LadderEntity>
```

For WRITE, `ElementType` is `WriteVarBasic`, descriptor `%WRITE_VAR0`, Column3. There is **no explicit width, height, Execute label, Abort label or output-pin child** in these GP entities. Upstream grid cells are ordinary contacts/lines with `ChosenConnection`=`Left, Right`. The read block is preceded by contact `%M3` at column0 and a Line at column1. The write block is preceded by a Line at column0, contact `%M2` at column1 and a Line at column2.

The original GP rungs contain only the Execute input and no connected outputs:

```text
BLK   %READ_VAR0
LD    %M3
EXECUTE
END_BLK
```

GP does not establish the actual multirow graphical output geometry, pin row offsets or required width when Abort/output pins are connected. G pp.177/181 independently documents IL with `EXECUTE`, `ABORT`, `OUT_BLK`, `LD DONE`, `LD BUSY`, `LD ABORTED`, `LD ERROR`, `END_BLK`. Use the **full** names; D/B/A/E aliases are not established by the communication example. A timer's D output naming does not establish the communication output name.

GP watchlist lines955-1015 confirms these public object suffixes:

```text
.OBJTYPE .FIRSTOBJ .QUANTITY .INDEXDATA .LINK .ID .TIMEOUT
.COMMERROR .OPERERROR .DONE .BUSY .ABORTED .ERROR
```

## Ethernet remote servers

WS establishes this complete nesting:

```text
ProjectDescriptor/HardwareConfiguration/Plc/Cpu/EthernetConfiguration/
  ModbusTcpSlave/Devices/RemoteServer
```

The observed RemoteServer subtree is:

```xml
<RemoteServer>
  <DeviceId>0</DeviceId>
  <Address />
  <DeviceGeneralType>IoScannerOther</DeviceGeneralType>
  <DeviceTypeName>Generic Device</DeviceTypeName>
  <DeviceTypeId>23</DeviceTypeId>
  <SlaveAddress>10.0.0.3</SlaveAddress>
  <ResetVariable />
  <Name>Device 0</Name>
  <InitRequestUnitId>255</InitRequestUnitId>
  <ChannelUnitId>255</ChannelUnitId>
  <Timeout>10</Timeout>
</RemoteServer>
```

The FB's `RemoteDeviceId` is1 while the corresponding remote server `DeviceId` is0. This supports a one-based FB index to zero-based serialized device index in this example. A validator should establish this mapping explicitly rather than confuse the index with the Modbus Unit ID. `SlaveAddress` stores the IP; the serialized Unit ID names are `InitRequestUnitId` and `ChannelUnitId`, not the FB parameter `RemoteDeviceId`.

The same parent ModbusTcpSlave contains SlavePort502 and UnitId247, plus HoldingRegister10 and InputRegister10. Those are local Modbus TCP server/mapping fields. **No remote destination port child occurs in the RemoteServer example.** Do not treat local `SlavePort` as the remote destination port; non502 remote destination authoring remains unproved.

The RemoteServer has no channels or init requests in this example; parent `IsIoScanner` isfalse. EthernetConfiguration itself includes FixedAddress, local IpAddress, SubnetMask, GatewayAddress, `TransfertRateAuto`, `ProtocolEthernet2` and a separate `ModbusServerEnabled` flag. GP proves the same broad Ethernet tree on CE40R but has an empty Devices list. Neither file establishes a complete CE40T hardware profile.

## Documented operation contract

The following is a paraphrase of G pp.171-181,204-205; it is independent of the project examples.

| Field or action | Contract |
|---|---|
| Execute | Rising edge starts a request; another edge during an active request is ignored. |
| Abort | Rising edge cancels execution, sets Aborted and CommError0x02. The timing diagram leaves Errorfalse on abort. |
| First RUN scan | TRUE at entry does not count as an edge; each input must first be observed false. |
| Busy | Remains true until completion even when Execute falls before the response. |
| Terminal output reset | Done/Error/Aborted stay asserted after completion while Execute remains true; clear when Execute falls. If Execute is already false on completion, the terminal result lasts one cycle. |
| Port sharing | Only one active communication FB/EXCH transaction per communication port; concurrent transactions must report an error instead of silently succeeding. |
| Timeout | Units100ms; default100 means10s; zero disables expiry. Expiry produces CommError1 and late responses are ignored. FB timeout overrides port configuration timeout. |
| Serial ID | READ1..247; WRITE additionally supports0 broadcast with no response expected. |
| Ethernet ID | Index1..16, distinct from the remote server's wire Unit ID. |
| FirstObj | Remote start address0..65535. Independently validate complete requested remote range rather than integer wraparound. |
| IndexData | First local memory word0..7999. Validate the entire local buffer; bits are packed into words from bit0. |
| Writable object fields | LINK, ID, TIMEOUT, OBJTYPE, FIRSTOBJ, QUANTITY, INDEXDATA. The offline configuration dialog's online-edit restriction does not make these runtime objects read-only. |
| Read-only fields | COMMERROR, OPERERROR, DONE, BUSY, ABORTED, ERROR. |
| Error widths | CommError is BYTE; OperError is DWORD. Their different widths must not be flattened without definition. |

Timing pages204/205 were rendered locally with Poppler and visually inspected. G p.205 text mentions Abort in a one-cycle sentence, but the actual signal drawing shows the **Aborted output** pulsing; input Abort remains high. The drawing resolves that textual ambiguity.

| Operation | Numeric OBJTYPE | Modbus code | Quantity |
|---|---:|---|---|
| Read holding words | 0 | 0x03 | 1..125 |
| Read input bits | 1 | 0x02 | 1..2000 |
| Read output bits | 2 | 0x01 | 1..2000 |
| Read input words | 3 | 0x04 | 1..125 |
| Write holding words | 0 | 0x10 | 1..123 |
| Write output bits | 2 | 0x0F | 1..1968 |
| Write one output bit | 4 | 0x05 | Quantity ignored; FL>=5.0 |
| Write one holding word | 5 | 0x06 | Quantity ignored; FL>=5.0 |

READ_VAR as a whole is not shown as FL>=5.0 in G. The explicit FL5.0 gate is for WRITE_VAR single-coil/single-register function codes. Do not apply that gate to all READ_VAR/WRITE_VAR instances without another source.

Existing M200 capability audit P25 reports16 instances per READ/WRITE/WRITE_READ type for functional level below10.1,32 for at least10.1. GP's actual TechnicalConfiguration/ComConfiguration contains32 for each type and16 SEND_RECV. WS's model/version records16 for each type even with FL11.0. Therefore the raw template values alone are not a universal model-independent budget rule; apply M200-specific documented limits and preserve source profile identity.

## Error-code interpretation

G pp.173-174 establishes CommError1 timeout,2 abort,3 malformed address,4 wrong remote address,5 management-table problem,6 invalid parameters,7 send failure,9 receive-buffer shortage,10 send-buffer shortage,11 unavailable system resource,14 length error,254 Modbus exception,255 refused request. Zero indicates communication success, but OperError must also be checked: CommError0 with OperError1 means unprocessed, and with OperError2 means bad response.

For CommError254, OperError is the Modbus exception code, including1 illegalfunction,2 invalidaddress,3 invalidvalue,4 devicefailure,5 acknowledgement,6 busy,8 memoryparity,10 gatewaypath and11 gatewaytarget. For CommError255, the documented operation values include1 missingtargetresource,5 length,6 channel,7 address,11 systemresource,12 inactivecommunication,13 unreachabletarget and15 unconfiguredchannel.

## Boundaries to preserve in implementation and claims

- Keep original controller references and original downloaded bytes/identities distinguishable from local normalized text and derived templates.
- Export the proven typed wrappers and enum strings; fail explicitly for unproven enum serialization rather than outputting guesses.
- Distinguish local request-simulation success from a real Modbus socket/serial exchange, and both from official editor or PLC validation.
- Retain timing, cancellation, late-response rejection and port contention in the simulator; do not use a stub that asserts Done merely because Execute istrue.
- Validate word and packed-bit buffer endpoints, dynamic property changes, ranges and numeric overflows before any transfer.
- No authentic complete CE40T profile, editor acceptance, actual on-PLC scheduling, real link reliability, multiple remote-server indexing, non502 remote ports or connected Abort/output Ladder geometry was proved by these examples.

All work in this sub-audit was local/read-only except creating this note and temporary evidence files. No CI, workflow, remote build, SSH, firmware operation or PLC download was run.

## Subsequent local serializer implementation

`m200/communication_xml.py` now reads and writes the observed typed READ_VAR / WRITE_VAR subset, validates serial configuration and remote-server records, and checks required template ports and instance budgets. Its unit tests use independent miniature XML builders; downloaded projects were not converted into synthetic CE40T fixtures. Direct read-only probes also recovered the original GP SL1 blocks, WS Ethernet block/remote server and LP IW block with their expected values.

The serializer intentionally has narrower coverage than the local Modbus runtime/PDU layer:

- XML authoring supports READ_VAR with MW or IW, and WRITE_VAR with MW. Bit objects, single writes and WRITE_READ_VAR have local runtime/PDU support but their XML serialization still fails explicitly because their raw enum/block payload was not proved here.
- Serial XML accepts only observed Baud9600/Baud19200, ParityEven/ParityNone, DataBits8, StopBits1, PhysicalMediumRs485 and TransmissionModeModbusRtu. ModemReference is limited to No Modem. This is a serialization allowlist, not the full documented physical serial capability range.
- Both observed master/slave Addressing enums can be preserved, but using an SL1 communication block requires explicit MasterAddressing, RS485, RTU and line-format fields. Port settings are never created automatically.
- Remote-server records require the observed Generic Device shape, numeric unicast IPv4 and a distinct one-based FB index / zero-based DeviceId. Port502 is implicit; custom remote destination ports are refused as unknown XML fields.
- Block parameter wrappers carry System.Int32 and are bounded to its nonnegative range before export. Full local/remote buffer spans retain the stricter ModbusConfig bounds.
- Functional-level names currently require the explicit `FunctLevelManN_N` spelling. GP's actual `FunctLevelMan18_0` is accepted as18.0; a legacy spelling without the underscore is not inferred. The CE40T editor/profile validation gap remains open regardless of that local parsing result.

Fifteen focused XML tests passed locally after observed RED/GREEN cycles. This verifies the closed local contract; it does not promote the editor or hardware validation status.
