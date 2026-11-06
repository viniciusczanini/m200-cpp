"""Explicit test-owned host bindings; no real I/O and no expected-data access."""

import os
import shutil
import subprocess
import sys


def timer_lifecycle(*, engine, request, repo, work):
    if engine == "sdk":
        return timer_sdk_lifecycle(request,repo,work)
    if engine != "vm":
        raise ValueError("Unknown timer backend")
    sys.path.insert(0, str(repo))
    from m200.il import Machine
    from m200.model import Program, Timer

    config = request["timer"]
    index = config["index"]
    reference = "%TM" + str(index)
    program = Program([
        ["LD %I0.0", "IN " + reference],
        ["LD 1", "[%MW0:=" + reference + ".V]"],
        ["LD " + reference + ".Q", "ST %Q0.0"],
    ], timers={index:Timer(config["kind"],config["base_ms"]*config["preset"],config["base_ms"],
                           config.get("retentive",False),config.get("dynamic",False))})
    machine = Machine(program)
    observations = []
    for event in request["events"]:
        if "event" in event:
            machine.timer_event(event["event"])
        elif "advance_ms" in event:
            machine.advance_time(event["advance_ms"])
        elif "set_preset" in event:
            machine.timers[index].set_preset(event["set_preset"],machine.now)
        elif "scan" in event:
            machine.step({0:event["scan"]},dt_ms=0)
            observations.append({"value":machine.words[0],"done":bool(machine.outputs[0])})
        elif "probe" in event:
            timer = machine.timers[index]
            observations.append({"value":timer.read("V",machine.now),"done":bool(timer.read("Q",machine.now))})
        else:
            raise ValueError("Unknown explicit timer host event")
    if request["scenario"] == "timer_only_cold":
        return {"preset":machine.timers[index].read("P",machine.now),**observations[-1]}
    return observations


def timer_sdk_lifecycle(request,repo,work):
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if compiler is None:
        raise AssertionError("clang++ missing; this is not a skipped semantic case")
    config = request["timer"]
    kind = {"TON":"Ton","TOF":"Tof","TP":"Pulse"}[config["kind"]]
    true_false = lambda value:"true" if value else "false"
    cold = request["scenario"] == "timer_only_cold"
    show = 'std::printf("%d %d %d",timer.preset(),timer.value(),timer.done()?1:0);std::putchar(10);' if cold else 'std::printf("%d %d",timer.value(),timer.done()?1:0);std::putchar(10);'
    events = {"stop":"stop","run":"run","power_off":"power_off","warm_restart":"warm_restart","cold_restart":"cold_restart"}
    actions = []
    for event in request["events"]:
        if "event" in event:
            actions.append("plc::detail::timer_event(plc::detail::TimerEvent::"+events[event["event"]]+");")
        elif "advance_ms" in event:
            actions.append("plc::detail::timer_advance_time("+str(event["advance_ms"])+");")
        elif "set_preset" in event:
            actions.append("timer.set_preset("+str(event["set_preset"])+");")
        elif "scan" in event:
            actions.extend(["timer.update("+true_false(event["scan"])+");",show])
        elif "probe" in event:
            actions.append(show)
        else:
            raise ValueError("Unknown explicit SDK timer event")
    source = work/"timer-host.cpp"
    source.write_text("#include <cstdio>\n#define PLC_NATIVE\n#include <plc.hpp>\nint main(){plc::"+kind+" timer{"+
                      ",".join([str(config["index"]),str(config["base_ms"]),str(config["preset"]),true_false(config.get("retentive",False)),true_false(config.get("dynamic",False))])+"};\n"+
                      "\n".join(actions)+"\n}\n")
    binary = work/"timer-host"
    compiled = subprocess.run([compiler,"-std=c++17","-O0","-I",str(repo/"sdk"),str(source),"-o",str(binary)],capture_output=True,text=True,timeout=60)
    if compiled.returncode:
        raise AssertionError("SDK timer host does not compile:\n"+compiled.stderr)
    completed = subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
    if completed.returncode:
        raise AssertionError("SDK timer host failed:\n"+completed.stderr)
    rows = [[int(value) for value in line.split()] for line in completed.stdout.splitlines()]
    width = 3 if cold else 2
    if any(len(row)!=width for row in rows):
        raise AssertionError("Unexpected timer host observation width")
    if cold:
        return {"preset":rows[-1][0],"value":rows[-1][1],"done":bool(rows[-1][2])}
    return [{"value":row[0],"done":bool(row[1])} for row in rows]


class ScriptedTransport:
    """Literal response injection for the real CommunicationEngine under test.

    This class has no PLC state machine, parameter snapshots, result decoding,
    retry logic, peer model, status calculation, or expected-result assertions.
    Production owns all those effects; the transport supplies bytes only.
    """

    def __init__(self):
        self.tokens = set()
        self.sequence = 0
        self.incoming = None
        self.requests = []

    def start(self, config, pdu, now_ms):
        self.sequence += 1
        self.tokens.add(self.sequence)
        self.requests.append(bytes(pdu))
        return self.sequence

    def poll(self, token, now_ms):
        if token not in self.tokens:
            raise AssertionError("Production polled a canceled test transport token")
        if self.incoming is None:
            return None
        result, self.incoming = self.incoming, None
        self.tokens.remove(token)
        return result

    def cancel(self, token):
        self.tokens.discard(token)


def modbus_async(*, engine, request, repo, work):
    if engine != "vm":
        raise ValueError("No SDK transport state-machine oracle is supplied by a communication_hook stub")
    sys.path.insert(0, str(repo))
    from m200.modbus import CommunicationEngine, ModbusConfig

    transport = ScriptedTransport()
    communication = CommunicationEngine(transport)
    config = ModbusConfig(**request["config"])
    communication.define("%READ_VAR0",config)
    words = [0]*8000
    for address,value in request["initial_words"].items():
        words[int(address)] = value
    final = None
    for position,event in enumerate(request["events"]):
        changes = event.get("set_property", {})
        if changes:
            if set(changes) != {"IndexData"}:
                raise ValueError("Unbound property in semantic request")
            communication.write_property("%READ_VAR0","INDEXDATA",changes["IndexData"])
        incoming = event.get("transport_response_hex",event.get("late_response_hex"))
        transport.incoming = None if incoming is None else bytes.fromhex(incoming)
        final = communication.update("%READ_VAR0",config,event.get("execute",False),event.get("abort",False),position*10,words)
    result = {"words":{address:words[int(address)] for address in request["initial_words"]},"done":bool(final.done)}
    if request["scenario"] == "busy_config_snapshot":
        result.update(request_hex=transport.requests[0].hex().upper(),error=bool(final.error),
                      configured_index_data=communication.read_property("%READ_VAR0","INDEXDATA"))
    elif request["scenario"] == "abort_late_response":
        result["aborted"] = bool(final.aborted)
    else:
        raise ValueError("Unknown explicit Modbus semantic scenario")
    return result
