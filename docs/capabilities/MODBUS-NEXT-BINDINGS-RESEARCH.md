# Next Modbus SMBP bindings: evidence and preparation

Research date: 2026-11-06. This note prepares the next closed bindings beyond READ_VAR MW/IW and WRITE_VAR MW. It does not change their current export gates or reduce the full parity objective. Work was limited to local manuals, static installed metadata and downloaded authored projects; no editor, Wine, simulator, network probe or external endpoint was operated.

## Reproducible sources

| Source | Identity and use |
|---|---|
| [Generic Functions Library EIO0000003289.04](https://www.se.com/ww/en/download/document/EIO0000003289/) | Local PDF SHA256 `d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595`; printed pp.175, 180, 183–187. Parameter tables and block illustration were checked against rendered pages. |
| [M100/M200 Programming Guide EIO0000002019.06](https://www.se.com/ww/en/download/document/EIO0000002019/) | Local PDF SHA256 `fb4f684e7efbb46e3e38e61ed532d99bf623bedffe447b5c379dd3dd6c4434df`; M200 server address spaces and FC23/`0x17` tables. |
| Installed Machine Expert Basic 1.4 build484 | `SchneiderElectric.SoMachineBasic.Entities.dll`, SHA256 `bf7b33a79356dbfd9839891b00e61695b5af3b5ee7ce121def37e3e973a9455e`. Static type, enum, property, parameter-factory and pin-construction facts only. No vendor binary or method body is reproduced here. |
| Installed English help | `Help/en-GB/sombgflg.chm`, SHA256 `b4e4ec3ba4e8770f6ec0e459e15ace5ade9cb811f5a7b68d13c3c17e5759272c`. The installed contextual-help index maps WRITE_READ_VAR and its configuration to topics `sombgflg_D-SE-0045502.htm` and `sombgflg_D-SE-0045503.htm`. This identifies documentation; it is not saved-project geometry evidence. |
| [Authored GP26 project](https://github.com/Mohammed-Helal/GP26/blob/0f68ca90f7fd51d44176b8bea01e73039c8e0641/Ladder_Code.smbp) | Local `research/downloads/public-projects/07-Ladder_Code.smbp`, SHA256 `fac44c53efcba56b5664d1cc59ce33d2fc230480a51351966066ed022b82eef7`; commit `0f68ca90f7fd51d44176b8bea01e73039c8e0641`, blob `2bed3b7e2aecc47d28adf0ca3d5e8d941bfd9cac`. Actual CPU is **TM200CE40R**. Establishes MW READ/WRITE serialization and Execute-only graphics, not the new cases below. |

All five hashes were freshly verified. The 25 SMBP files currently under `research/downloads` were parsed; their only READ_VAR/WRITE_VAR/WRITE_READ_VAR instances were the two GP26 MW blocks. Thus this local sample search yielded no authored bit, single-write or WRITE_READ_VAR binding. Older WS/LP word examples remain documented in [MODBUS-FORMAT-RESEARCH.md](MODBUS-FORMAT-RESEARCH.md); their temporary copies were unavailable for fresh comparison.

## Object types: documented meaning, not a name-based guess

The installed `FBComObjTypeParameterEnums` values and the manual's numeric tables agree as follows. Here the objects belong to the **remote Modbus address space**. Every `IndexData` identifies a **local MW buffer**, including bit exchanges; it does not select local physical I/Q pins.

| Installed enum | Value | READ_VAR | WRITE_VAR |
|---|---:|---|---|
| `MW` | 0 | Holding registers, FC3, 1..125 words | Multiple holding registers, FC16, 1..123 words |
| `I` | 1 | Digital inputs, FC2, 1..2000 bits | Not a documented WRITE object type |
| `Q` | 2 | Digital outputs/coils, FC1, 1..2000 bits | Multiple output bits, FC15, 1..1968 bits |
| `IW` | 3 | Input registers, FC4, 1..125 words | Not a documented WRITE object type |
| `SINGLE_COIL` | 4 | Not a documented READ object type | Single output bit, FC5; Quantity ignored |
| `SINGLE_REG` | 5 | Not a documented READ object type | Single register, FC6; Quantity ignored |

These mappings are explicit on pp.175 and 180. The documented M200 serial server maps FC1/2 to internal `%M`; the client enum names do not establish that a particular server exposes physical inputs or outputs. Bits use local MW words starting at bit 0: 17 bits require two words. Preserve separate remote-range and complete local-buffer bounds.

FC5/6 require functional level **5.0 or later** (p.180). That is not a general gate for FC1/2/15. The installed level mapping already recorded in [EDITOR-INTEROP-FACTS.json](EDITOR-INTEROP-FACTS.json) identifies 5.0 as `FunctLevelMan9_0`; numeric suffixes are not human levels.

WRITE_READ_VAR supports **MW only**, FC23 (`0x17`), with write quantity 1..121 and read quantity 1..125. The generic guide's p.185 wording “Fct17” must not be interpreted as decimal FC17; the M200 guide explicitly lists 23 (`17 hex`). Its outbound and inbound local buffers are distinct parameters.

## WRITE_READ_VAR: static binding facts and remaining proof

Installed namespace prefix is `SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks.`. Type `Com.WriteReadVarBasic` (TypeDef577) derives from `Com.ComFunctionBlockBase`, just like READ/WRITE. Its `BuildParameters` method (metadata token `0x06001790`) constructs the following parameters through `FunctionBlockParameterElementFactory.Create`:

| Parameter names | Constructed wrapper family | Expected value path; still needs an authored save |
|---|---|---|
| `ObjType` | ``FbParameterElementEnumType`1<Enums.FBComObjTypeParameterEnums>`` | `ObjType/Value/FBComObjTypeParameterEnums`, value `MW` |
| `FirstWriteObj`, `WriteQuantity`, `IndexDataOut` | ``FbParameterElementRangeType`1<System.Int32>`` | Each parameter's `Value/int`; outbound address, count and local source |
| `FirstReadObj`, `ReadQuantity`, `IndexDataIn` | Same Int32 range wrapper | Each parameter's `Value/int`; inbound address, count and local destination |
| Inherited `Link`, `RemoteDeviceId`, `Timeout` | Link enum wrapper; Int32 range wrappers | Same semantic fields as the established READ/WRITE binding |

The wrapper family follows the construction attribute and factory branches, not merely the properties' declared base return types. The latter are ``FbParameterElementBase`1<T>`` and alone would not prove a concrete wrapper. Existing authored READ/WRITE XML supplies the exact assembly-qualified range/enum `Type` strings in [MODBUS-FORMAT-RESEARCH.md](MODBUS-FORMAT-RESEARCH.md). Reusing those strings for WRITE_READ_VAR is a **candidate binding**, pending an editor-authored save; this inspection does not establish XML child order, omitted defaults or every serialization attribute. The installed link enum remains `SerialLine1=1`, `SerialLine2=2`, `EthernetLink=3`, `SerialLine3=4`; the SDK's Ethernet value 2 must not become XML SerialLine2.

The natural block-type candidate is the same assembly-qualified prefix plus `Com.WriteReadVarBasic`. The installed `ProgramElementTypes` enum also contains `WriteReadVarBasic=76`, alongside `ReadVarBasic=74` and `WriteVarBasic=75`. These are exact candidate names, without establishing the complete `IFunctionBlock` serialization or Ladder graph. `CommError` and `OperError` exist as inherited status parameters; their construction does not justify adding them to serialized configuration when established word examples omit them.

Raw generic metadata bounds are also insufficient: the WR read/write quantity attributes carry maxima 2000/1936 and local indices carry a generic 65535 bound, with contextual validators `IsValidComObjectType`, `IsValidComIndexData` and `IsValidQuantity`. **Do not promote those raw maxima to allowed word counts or local MW capacity.** Use the documented 125/121 and 0..7999 bounds, plus full extents, until authentic evidence establishes more.

The inherited pin construction (`BuildInputs` `0x060017c3`, `BuildOutputs` `0x060017c4`) and p.183 illustration agree on two inputs, Execute then Abort, and four outputs, Done, Busy, Aborted, Error. The picture aligns Execute/Done and Abort/Busy, with Aborted and Error below. This proves labels and conceptual placement, **not SMBP grid offsets, block width/height or `ChosenConnection` values**. The installed output enum's flags 1/2/4/8 are not grid-row offsets. The GP26 graph only places Execute-only ReadVarBasic at row 0/column 2 and WriteVarBasic at row 0/column 3 with `ChosenConnection=Left`; it has no Abort or connected output evidence.

## Smallest useful authentic capture set

The next GUI stage should save and reopen a genuine CE40T profile with an explicitly configured, already established link. It can collect the six cases in one labelled project, retaining an unchanged word-control project. Capture each configuration, raw file hash, relevant XML/IL and visible validation; do not infer successful communication from opening or saving.

| Case | Deliberate distinction | Binding evidence needed |
|---|---|---|
| READ I and READ Q | Separate instances; quantity 17; different remote starts and local MW buffers | Saved enum spellings `I`/`Q`, local MW buffer field and unchanged Execute-only graph shape |
| WRITE Q | Quantity 17, distinct local source | `Q` for multiple bits, without accidentally selecting the single-coil variant |
| WRITE single coil and single register | Two instances, distinct remote addresses and local sources | `SINGLE_COIL`/`SINGLE_REG`, actual saved Quantity/default treatment; compare availability and validation at FL4.0 and FL5.0 against the documented minimum |
| WRITE_READ MW | E.g. write start 17/count 2/local 300; read start 41/count 3/local 400 | Exact block Type, wrappers, child order and six asymmetric fields, detecting inbound/outbound swaps |

For each of the three block classes, retain a second graph with Abort and all four outputs wired to separate memory bits. This is needed before accepting such graphs; READ/WRITE graphics should not be assumed identical to WR just because the pin base class is shared. Preserve all actual row/column/descriptor/connection fields and compare raw IL with the closed normalized form. No external exchange is necessary to establish this serialization evidence; runtime and physical protocol validation remain separate stages owned by the authorized lab workflow.

After capture, the implementation follow-up can add one exact positive binding at a time, with rejection tests for wrong class/address/enum, duplicated or missing parameters, wrong wrappers/attributes, invalid READ/WRITE object combinations, FL5.0 single-write boundary, quantity and full-buffer extents, and contradictory or incomplete graph wiring. Each rejection must preserve the previous output. WR tests must use asymmetric read/write data and sizes, including overlap behavior already defined by the local model. This work must not broaden links, invent device configuration, infer runtime property editing, or remove unknown-form failures.

Current [communication_xml.py](../../m200/communication_xml.py) intentionally accepts only READ_VAR MW/IW and WRITE_VAR MW; [project.py](../../m200/project.py) also limits communication graphics. The local SDK/IL/VM/protocol support described in [MODBUS-PARITY-AUDIT.md](MODBUS-PARITY-AUDIT.md) remains useful but does not close these editor bindings or establish official runtime parity. No implementation files, gates or result manifests were changed by this research.
