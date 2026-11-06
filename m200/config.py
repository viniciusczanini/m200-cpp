"""Fail-closed configuration subset; opaque UI/capability data is not code."""

import re
from collections import Counter
from .model import fail
from .counter_xml import read_configs as read_counters
from .numeric import word_address
from .communication_xml import (
    allowed_attribute,
    read_blocks,
    validate_serial,
    validate_remotes,
)

SOFTWARE = set(
    "Pous Subroutines WatchLists CustomSymbols ConstantWordsMemoryAllocation MemoryBitsMemoryAllocation MemoryWordsMemoryAllocation TimersMemoryAllocation CountersMemoryAllocation RegistersMemoryAllocation DrumsMemoryAllocation SbrsMemoryAllocation ScsMemoryAllocation FcsMemoryAllocation SchsMemoryAllocation HscsMemoryAllocation PtosMemoryAllocation MemoryBits SystemBits SystemWords GrafcetSteps MemoryWords MemoryDoubleWords MemoryFloats ConstantWords ConstantDoubleWords ConstantMemoryFloats Timers Counters FastCounters Registers Drums ShiftBitRegisters StepCounters ScheduleBlocks Pids MessageBlocks FunctionBlocks MotionTaskTables FastTask MastTask CpuBehavior TraceTimeBase UserFunctionPous UserFunctionBlockPous UserDefineFunctionBlocks".split()
)
EMPTY = set(
    "Subroutines GrafcetSteps MemoryWords MemoryDoubleWords MemoryFloats ConstantWords ConstantDoubleWords ConstantMemoryFloats Counters FastCounters Registers Drums ShiftBitRegisters StepCounters ScheduleBlocks Pids FunctionBlocks MotionTaskTables UserFunctionPous UserFunctionBlockPous UserDefineFunctionBlocks".split()
)
EMPTY -= {"MemoryWords", "MemoryDoubleWords", "MemoryFloats"}
EMPTY.discard("FunctionBlocks")
EMPTY.discard("Counters")
UI_ONLY = {
    "DisplayUserLabelsConfiguration",
    "GlobalProperties",
    "ReportConfiguration",
    "WatchLists",
    "CustomSymbols",
}
ROOT = {
    "ProjectVersion",
    "ManagementLevel",
    "Name",
    "FullName",
    "CurrentCultureName",
    "SoftwareConfiguration",
    "HardwareConfiguration",
} | UI_ONLY
REPEATED = {
    "FunctionBlocks": {"IFunctionBlock"},
    "Devices": {"RemoteServer"},
    "RemoteServers": {"RemoteServer"},
    "Pous": {"ProgramOrganizationUnits"},
    "Rungs": {"RungEntity"},
    "InstructionLines": {"InstructionLineEntity"},
    "LadderElements": {"LadderEntity"},
    "Timers": {"TimerTM"},
    "Counters": {"Counter"},
    "MemoryBits": {"MemoryBit"},
    "MemoryWords": {"MemoryWord"},
    "MemoryDoubleWords": {"MemoryDoubleWord"},
    "MemoryFloats": {"MemoryFloat"},
    "SystemBits": {"MemoryBit"},
    "SystemWords": {"MemoryWord"},
    "MessageBlocks": {"MessageBlock"},
    "DigitalInputs": {"DiscretInput"},
    "DigitalOutputs": {"DiscretOutput"},
    "HighSpeedCounters": {"HighSpeedCounter"},
    "DedicatedInputs": {"DedicatedInput"},
    "ReflexOutputs": {"ReflexOutput"},
    "Thresholds": {"Threshold"},
}
CPU_SCALARS = set(
    "Index InputNb OutputNb Kind Reference Name Consumption5V Consumption24V HardwareId IsExpander MaxCartridge C1TranslationX C1TranslationY C2TranslationX C2TranslationY C1SizeX C1SizeY C2SizeX C2SizeY".split()
)
CPU_ARRAYS = set(
    "DigitalInputs DigitalOutputs AnalogInputs AnalogInputsStatus AnalogOutputs AnalogOutputsStatus HighSpeedCounters PulseTrainOutputs InputAssemblys OutputAssemblys InputRegisters HoldingRegisters".split()
)
TECHNICAL = set(
    "PtoConfiguration ComConfiguration Compatibility FastCounterMax FourInputsEventTask GrafcetBitsMax InternalRamStart LabelsMax LfRegistersMax MemoryConstantWordsMax MemoryWordsMax NumRelays NumRelaysMax NumTransistors NumTransistorsMax PidAmountMax PlcNumberSysBits PlcNumberSysWords PlcStartAddrSysBits PlcType TimersMax AnalogInputPrecision AnalogOutputPrecision StepCountersMax CountersMax DrumsMax ExternalRamSize ExternalRamSizeWithDisplay ExternalRamStart InternalRamAppStart InternalRamSize InternalBitsMax InternalEepromSize ScheduleBlocksMax ShiftBitRegistersMax SubroutinesMax SupportDoubleWord SupportEvents SupportFloatingPoint NumberOf1MsTimerBase".split()
)


def fields(node, allowed):
    for child in node:
        if child.tag not in allowed:
            fail("unsupported configuration field: " + node.tag + "/" + child.tag)


def scalar(node):
    if len(node):
        fail("configuration value must be scalar: " + node.tag)


def unique_tree(root):
    # Arrays may repeat only their entry type. Every other interpreted field is
    # a singleton, including fields nested inside each array entry.
    def visit(node, parents=()):
        if node.tag in UI_ONLY:
            return
        if len(node) and (node.text or "").strip():
            fail("configuration value must be scalar: " + node.tag)
        for attribute, value in node.attrib.items():
            in_fb = (
                node.tag == "IFunctionBlock"
                and parents
                == ("ProjectDescriptor", "SoftwareConfiguration", "FunctionBlocks")
            ) or parents == (
                "ProjectDescriptor",
                "SoftwareConfiguration",
                "FunctionBlocks",
                "IFunctionBlock",
            )
            if in_fb and allowed_attribute(node.tag, attribute, value):
                continue
            if not (
                node.tag == "UnitId"
                and attribute == "{http://www.w3.org/2001/XMLSchema-instance}nil"
                and value == "true"
                and not len(node)
                and not (node.text or "").strip()
            ):
                fail("unsupported XML attribute: " + node.tag + "/" + attribute)
        counts = Counter(c.tag for c in node)
        for tag, n in counts.items():
            if n > 1 and tag not in REPEATED.get(node.tag, set()):
                fail("duplicate XML singleton: " + node.tag + "/" + tag)
        for child in node:
            visit(child, parents + (node.tag,))

    visit(root)
    fields(root, ROOT)


def empty(node):
    if len(node) or (node.text or "").strip():
        fail("unsupported active configuration: " + node.tag)


def check_bits(node, kind, capacity):
    fields(node, {"MemoryBit" if kind != "SW" else "MemoryWord"})
    seen = set()
    for bit in node:
        fields(bit, {"Address", "Index", "Symbol", "Comment"})
        for c in bit:
            scalar(c)
        try:
            index = int(bit.findtext("Index", "-1"))
        except ValueError:
            fail("invalid memory metadata index")
        if (
            not 0 <= index < capacity
            or index in seen
            or bit.findtext("Address") != "%" + kind + str(index)
        ):
            fail("invalid or duplicate memory metadata")
        seen.add(index)


def check_io(node, entry, prefix, capacity):
    fields(node, {entry})
    seen = set()
    for io in node:
        fields(io, {"Address", "Index", "Symbol", "Comment"})
        for c in io:
            scalar(c)
        try:
            index = int(io.findtext("Index", "-1"))
        except ValueError:
            fail("invalid I/O index")
        if (
            not 0 <= index < capacity
            or index in seen
            or io.findtext("Address") != prefix + str(index)
        ):
            fail("invalid or duplicate I/O descriptor")
        seen.add(index)


def check_numbers(node):
    entry, prefix = {
        "MemoryWords": ("MemoryWord", "MW"),
        "MemoryDoubleWords": ("MemoryDoubleWord", "MD"),
        "MemoryFloats": ("MemoryFloat", "MF"),
    }[node.tag]
    fields(node, {entry})
    seen = set()
    for item in node:
        fields(item, {"Address", "Index", "Symbol", "Comment"})
        for child in item:
            scalar(child)
        addr = item.findtext("Address", "")
        _, index = word_address(addr)
        if (
            not addr.startswith("%" + prefix)
            or item.findtext("Index") != str(index)
            or index in seen
        ):
            fail("invalid or duplicate numeric memory metadata")
        seen.add(index)


def inactive_hsc(node):
    fields(node, {"HighSpeedCounter"})
    seen = set()
    for hsc in node:
        fields(
            hsc,
            {
                "Address",
                "Index",
                "Preset",
                "DedicatedInputs",
                "ReflexOutputs",
                "Thresholds",
                "TimeWindow",
                "Symbol",
                "Comment",
            },
        )
        index = hsc.findtext("Index", "")
        if (
            index not in ("0", "1", "2", "3")
            or index in seen
            or hsc.findtext("Address") != "%HSC" + index
        ):
            fail("invalid high-speed counter defaults")
        seen.add(index)
        if (
            hsc.findtext("Preset", "0") != "0"
            or hsc.findtext("TimeWindow", "OneSecond") != "OneSecond"
        ):
            fail("configured high-speed counters are unsupported")
        for part in hsc:
            if part.tag == "DedicatedInputs":
                fields(part, {"DedicatedInput"})
                for item in part:
                    fields(item, {"Index"})
                    if item.findtext("Index") not in ("0", "1", "2", "3"):
                        fail("unsupported dedicated input")
            elif part.tag == "ReflexOutputs":
                fields(part, {"ReflexOutput"})
                for item in part:
                    fields(
                        item,
                        {
                            "Index",
                            "Activated",
                            "LessThanS0",
                            "GreaterOrEqualThanS0",
                            "GreaterOrEqualThanS1",
                        },
                    )
                    if item.findtext("Index") not in ("0", "1"):
                        fail("invalid reflex output")
                    if any(
                        c.tag != "Index" and (c.text or "").lower() != "false"
                        for c in item
                    ):
                        fail("active reflex outputs are unsupported")
            elif part.tag == "Thresholds":
                fields(part, {"Threshold"})
                for item in part:
                    fields(
                        item, {"Index", "ThresholdType", "Priority", "SubroutineNumber"}
                    )
                    if (
                        item.findtext("Index") not in ("0", "1")
                        or item.findtext("ThresholdType", "NotUsed") != "NotUsed"
                        or item.findtext("Priority", "7") != "7"
                        or item.findtext("SubroutineNumber", "")
                    ):
                        fail("active high-speed counter threshold is unsupported")
            else:
                scalar(part)


def ethernet(node):
    simple = set(
        "NetworkName IpAllocationMode IpAddress SubnetMask GatewayAddress TransfertRate EthernetProtocol ProgrammingProtocolEnabled EthernetIpAdapterEnabled ModbusServerEnabled AutoDiscoveryProtocolEnabled".split()
    )
    fields(node, simple | {"ModbusTcpSlave", "EthernetIpEntity"})
    for part in node:
        if part.tag in simple:
            scalar(part)
        elif part.tag == "ModbusTcpSlave":
            fields(
                part,
                {
                    "IpMasterAddress",
                    "UseTimeout",
                    "Timeout",
                    "SlavePort",
                    "UnitId",
                    "HoldingRegister",
                    "InputRegister",
                    "RemoteServers",
                    "ModbusServerEnabled",
                    "Devices",
                    "DigitalInputsIoScanner",
                    "DigitalOutputsIoScanner",
                    "RegisterInputsIoScanner",
                    "RegisterOutputsIoScanner",
                    "RegisterDeviceStatusIoScanner",
                    "RegisterInputsStatusIoScanner",
                    "Drives",
                    "IsIoScanner",
                },
            )
            for c in part:
                if c.tag in ("RemoteServers", "Devices"):
                    validate_remotes(c)
                elif c.tag.endswith("IoScanner") or c.tag == "Drives":
                    empty(c)
                elif c.tag == "IsIoScanner":
                    scalar(c)
                    if (c.text or "false").lower() != "false":
                        fail("active IOScanner configuration is not implemented")
                else:
                    scalar(c)
            if (
                part.findtext("HoldingRegister", "0") != "0"
                or part.findtext("InputRegister", "0") != "0"
                or part.findtext("ModbusServerEnabled", "false").lower() != "false"
            ):
                fail("active Modbus mapping is unsupported")
        else:
            fields(
                part,
                {
                    "EthernetIpEnabled",
                    "OutputAssemblyInstance",
                    "OutputAssemblySize",
                    "InputAssemblySize",
                    "InputAssemblyInstance",
                },
            )
            for c in part:
                scalar(c)
                if c.tag == "EthernetIpEnabled":
                    if (c.text or "").lower() != "false":
                        fail("active EtherNet/IP mapping is unsupported")
                elif (c.text or "") != "0":
                    fail("active EtherNet/IP assembly is unsupported")


def configuration(root):
    unique_tree(root)
    hw = root.find("HardwareConfiguration")
    fields(hw, {"Plc"})
    plc = hw.find("Plc")
    plc_metadata = set(
        "Power5VCapacities Power24VCapacities Power5VTotalConsumption Power24VTotalConsumption ExpanderPower5VCapacities ExpanderPower24VCapacities ExpanderPower5VTotalConsumption ExpanderPower24VTotalConsumption".split()
    )
    fields(
        plc,
        {
            "Cpu",
            "Extensions",
            "SerialLineConfiguration",
            "SerialLineIoScannerConfiguration",
        }
        | plc_metadata,
    )
    for part in plc:
        if part.tag == "SerialLineConfiguration" and len(part):
            validate_serial(part)
        elif part.tag == "SerialLineIoScannerConfiguration":
            fields(
                part,
                {
                    "TransmissionMode",
                    "Devices",
                    "DigitalInputsIoScanner",
                    "DigitalOutputsIoScanner",
                    "RegisterInputsIoScanner",
                    "RegisterOutputsIoScanner",
                    "RegisterDeviceStatusIoScanner",
                    "RegisterInputsStatusIoScanner",
                    "Drives",
                },
            )
            for c in part:
                if c.tag == "TransmissionMode":
                    scalar(c)
                    if c.text != "TransmissionModeRtu":
                        fail("unproven serial IOScanner mode")
                else:
                    empty(c)
        elif part.tag in ("Extensions", "SerialLineConfiguration"):
            empty(part)
        elif part.tag in plc_metadata:
            scalar(part)
    cpu = plc.find("Cpu")
    fields(
        cpu,
        CPU_SCALARS | CPU_ARRAYS | {"TechnicalConfiguration", "EthernetConfiguration"},
    )
    for part in cpu:
        if part.tag in CPU_SCALARS:
            scalar(part)
        elif part.tag == "DigitalInputs":
            check_io(part, "DiscretInput", "%I0.", 24)
        elif part.tag == "DigitalOutputs":
            check_io(part, "DiscretOutput", "%Q0.", 16)
        elif part.tag == "HighSpeedCounters":
            inactive_hsc(part)
        elif part.tag == "EthernetConfiguration":
            ethernet(part)
        elif part.tag == "TechnicalConfiguration":
            fields(part, TECHNICAL)
            for capability in part:
                if capability.tag in ("PtoConfiguration", "ComConfiguration"):
                    for c in capability:
                        if not c.tag.endswith("Max") or not re.fullmatch(
                            r"\d+", c.text or ""
                        ):
                            fail("unsupported capability metadata")
                        scalar(c)
                else:
                    scalar(capability)
        else:
            empty(part)
    sw = root.find("SoftwareConfiguration")
    if sw is None:
        fail("missing SoftwareConfiguration")
    fields(sw, SOFTWARE)
    read_counters(sw)
    for part in sw:
        if part.tag == "FunctionBlocks":
            read_blocks(sw)
        elif part.tag in EMPTY:
            empty(part)
        elif part.tag.endswith("MemoryAllocation"):
            fields(part, {"Allocation", "ForcedCount"})
            for c in part:
                scalar(c)
            if part.findtext("Allocation", "") not in ("", "Automatic", "Manual"):
                fail("unsupported memory allocation mode")
        elif part.tag == "MemoryBits":
            check_bits(part, "M", 1024)
        elif part.tag in ("MemoryWords", "MemoryDoubleWords", "MemoryFloats"):
            check_numbers(part)
        elif part.tag == "SystemBits":
            check_bits(part, "S", 160)
        elif part.tag == "SystemWords":
            check_bits(part, "SW", 234)
        elif part.tag == "MessageBlocks":
            fields(part, {"MessageBlock"})
            for item in part:
                fields(item, {"Address", "Index", "OutputPort"})
                for c in item:
                    scalar(c)
                triple = (
                    item.findtext("Address"),
                    item.findtext("Index"),
                    item.findtext("OutputPort"),
                )
                if triple not in (
                    ("%MSG1", "0", "Serial1"),
                    ("%MSG3", "2", "Ethernet"),
                ):
                    fail("configured message blocks are unsupported")
        elif part.tag == "FastTask":
            fields(part, {"Period"})
            for c in part:
                scalar(c)
            if part.findtext("Period", "255") != "255":
                fail("active fast task is unsupported")
        elif part.tag == "MastTask":
            fields(part, {"UsePeriodScanMode", "PeriodScan"})
            for c in part:
                scalar(c)
        elif part.tag == "CpuBehavior":
            fields(
                part,
                {
                    "StartingMode",
                    "RunStopAddress",
                    "AutoSaveRamOnEeprom",
                    "WatchdogPeriod",
                },
            )
            for c in part:
                scalar(c)
            if part.findtext("RunStopAddress", ""):
                fail("configured Run/Stop input is unsupported")
        elif part.tag == "Pous":
            fields(part, {"ProgramOrganizationUnits"})
        elif part.tag == "TraceTimeBase":
            scalar(part)
    return sw
