"""Real SDK raw-PDU binding; requests contain stimuli, never expectations.

The C++ transport copies requests and injects literal bytes/pending/errors only.
It has no Modbus codec, PLC status machine, word-store logic or retry logic.
"""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


class SDKExecutionError(AssertionError):
    def __init__(self, result):
        self.returncode, self.stderr = result.returncode, result.stderr
        super().__init__("SDK host exited %s: %s" % (result.returncode, result.stderr))


TRANSPORT = r'''
using namespace plc::detail;
struct Flight { ModbusToken token; const unsigned char* pointer; unsigned size; std::vector<unsigned char> copy; bool active=true,cancelled=false; };
struct Script { ModbusToken next=0; unsigned cancels=0; std::vector<Flight> flights; };
struct Stimulus { ModbusPollKind kind=ModbusPollKind::Pending; std::vector<unsigned char> bytes; unsigned size=0; int comm=255,oper=6; bool accepted=true; } stimulus;
struct Request { std::vector<unsigned char> bytes; int id,link; };
std::vector<Request> recorded;
void fail_host(const char* reason){std::fprintf(stderr,"HOST:%s\n",reason);std::exit(71);}
void check_pointer(const Flight& f){if(f.size!=f.copy.size()||std::memcmp(f.pointer,f.copy.data(),f.size))fail_host("SDK request changed while active");}
Flight& flight(Script& s,ModbusToken token){for(auto& f:s.flights)if(f.token==token)return f;fail_host("unknown token/context");std::abort();}
ModbusStartResult raw_start(void* context,const CommunicationConfig& config,const unsigned char* data,unsigned size,unsigned long long){
    std::fputs("RAW_START\n",stderr);
    if(size>253||!data)fail_host("invalid SDK request buffer");
    recorded.push_back({std::vector<unsigned char>(data,data+size),config.id,config.link});
    if(!stimulus.accepted)return {false,0,(plc::i16)stimulus.comm,(plc::i32)stimulus.oper};
    auto& s=*static_cast<Script*>(context);ModbusToken token=s.next++;
    s.flights.push_back({token,data,size,std::vector<unsigned char>(data,data+size),true,false});
    return {true,token,0,0};
}
ModbusPollResult raw_poll(void* context,ModbusToken token,unsigned long long,unsigned char* data,unsigned capacity){
    auto& f=flight(*static_cast<Script*>(context),token);
    if(!f.active||f.cancelled)fail_host("polled retired token");
    check_pointer(f);
    if(capacity!=253)fail_host("unexpected PDU receive capacity");
    unsigned count=(unsigned)stimulus.bytes.size();
    if(count>capacity)count=capacity;
    if(count)std::memcpy(data,stimulus.bytes.data(),count);
    if(stimulus.kind!=ModbusPollKind::Pending)f.active=false;
    return {stimulus.kind,stimulus.size,(plc::i16)stimulus.comm,(plc::i32)stimulus.oper};
}
void raw_cancel(void* context,ModbusToken token){
    auto& s=*static_cast<Script*>(context);auto& f=flight(s,token);
    if(f.active)check_pointer(f);
    if(f.cancelled)fail_host("duplicate cancellation");
    f.active=false;f.cancelled=true;++s.cancels;
}
struct Snapshot { const char* name; bool done,busy,aborted,error; int comm,oper; };
std::vector<Snapshot> snapshots;
void capture(const char* name,const plc::Communication& block){snapshots.push_back({name,block.done(),block.busy(),block.aborted(),block.error(),block.comm_error(),block.oper_error()});}
'''


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Invalid test stimulus integer")
    return str(value)


def _word_writes(words):
    return ["plc::write_word(%s,(plc::i16)(unsigned short)%s);" % (
        _integer(int(index), 0, 7999), _integer(value, -32768, 65535)) for index, value in words.items()]


def _configuration(name, config, index):
    if re.fullmatch(r"[a-z][a-z0-9_]*", name) is None:
        raise ValueError("Invalid test block identity")
    cls = {"READ_VAR": "ReadVar", "WRITE_VAR": "WriteVar", "WRITE_READ_VAR": "WriteReadVar"}[config.get("kind", "READ_VAR")]
    link = {"SL1": "Serial1", "ETH1": "Ethernet"}[config.get("link", "SL1")]
    args = [str(index), "plc::Link::" + link, str(config.get("id", 1)), str(config.get("timeout_100ms", 100))]
    if cls != "WriteReadVar":
        obj = {0: "HoldingWords", 1: "DiscreteInputs", 2: "Coils", 3: "InputWords", 4: "SingleCoil", 5: "SingleRegister"}[config.get("obj_type", 0)]
        args.append("plc::Object::" + obj)
    args += [str(config.get("first_obj", 0)), str(config.get("quantity", 1)), str(config.get("index_data", 0))]
    if cls == "WriteReadVar":
        args += [str(config.get("first_read_obj", 0)), str(config.get("read_quantity", 1)), str(config.get("index_data_in", 0))]
    return "plc::%s %s{%s};" % (cls, name, ",".join(args))


def _source(request):
    blocks = request["blocks"]
    lines = ["#include <cstdio>", "#include <cstdlib>", "#include <cstring>", "#include <vector>",
             "#define PLC_NATIVE", "#include <plc.hpp>", TRANSPORT, "int main(){plc::WordMemory image{8000};Script natal_raw_primary,natal_raw_alternate;"]
    for index, (name, config) in enumerate(blocks.items()):
        lines.append(_configuration(name, config, config.get("native_index", index)))
    mode = request.get("transport", "raw")
    if mode != "none":
        lines.append("plc::detail::modbus_transport={&natal_raw_primary,raw_start,%s,raw_cancel};" % ("nullptr" if mode == "partial" else "raw_poll"))
    lines += _word_writes(request.get("initial_words", {}))
    for index, mask in request.get("poison_words", {}).items():
        lines.append("plc::detail::indeterminate_words[%s]=%s;" % (_integer(int(index), 0, 7999), _integer(mask, 0, 65535)))
    if request.get("sticky_flags"):
        lines += ["plc::detail::arithmetic_error=true;plc::detail::shift_carry=true;plc::detail::float_status=4;"]
    previous = 0
    for position, event in enumerate(request["events"]):
        now = event.get("now_ms", position * 10)
        if type(now) is not int or now < previous:
            raise ValueError("Test clock must be monotonic")
        previous = now
        lines.append("plc::detail::now_ms=%s;" % now)
        poll = event.get("poll", {})
        payload = bytes.fromhex(poll.get("hex", ""))
        kind = {"pending": "Pending", "response": "Response", "broadcast": "BroadcastComplete", "error": "Error"}[poll.get("kind", "pending")]
        lines.append("stimulus={};stimulus.kind=ModbusPollKind::%s;stimulus.bytes={%s};stimulus.size=%s;stimulus.comm=%s;stimulus.oper=%s;stimulus.accepted=%s;" % (
            kind, ",".join(str(b) for b in payload), poll.get("size", len(payload)), poll.get("comm_error", 255), poll.get("oper_error", 6), "false" if event.get("start_error") else "true"))
        if event.get("start_error"):
            lines.append("stimulus.comm=%s;stimulus.oper=%s;" % tuple(event["start_error"]))
        if event.get("rebind_transport"):
            lines.append("plc::detail::modbus_transport={&natal_raw_alternate,raw_start,raw_poll,raw_cancel};")
        lines += _word_writes(event.get("write_words", {}))
        for change in event.get("set_properties", []):
            name, field, value = change
            if name not in blocks or field not in ("Link", "Id", "Timeout", "ObjType", "FirstObj", "Quantity", "IndexData", "FirstWriteObj", "WriteQuantity", "IndexDataOut", "FirstReadObj", "ReadQuantity", "IndexDataIn"):
                raise ValueError("Unknown property stimulus")
            lines.append("%s.set_property(plc::CommProperty::%s,(plc::i16)(unsigned short)%s);" % (name, field, _integer(value, -32768, 65535)))
        for call in event.get("calls", []):
            name = call["block"]
            if name not in blocks:
                raise ValueError("Unknown called block")
            lines.append("%s.update(%s,%s);" % (name, "true" if call.get("execute", False) else "false", "true" if call.get("abort", False) else "false"))
        for name in event.get("capture", []):
            if name not in blocks:
                raise ValueError("Unknown observed block")
            lines.append('capture("%s",%s);' % (name, name))
    lines.append('std::printf("{\\\"request_hexes\\\":[");for(unsigned i=0;i<recorded.size();++i){if(i)std::putchar(44);std::putchar(34);for(unsigned char b:recorded[i].bytes)std::printf("%02X",(unsigned)b);std::putchar(34);}std::printf("],\\\"request_ids\\\":[");')
    lines.append('for(unsigned i=0;i<recorded.size();++i){if(i)std::putchar(44);std::printf("%d",recorded[i].id);}std::printf("],\\\"request_links\\\":[");for(unsigned i=0;i<recorded.size();++i){if(i)std::putchar(44);std::printf("%d",recorded[i].link);}std::printf("],\\\"statuses\\\":{");')
    for index, name in enumerate(blocks):
        prefix = "," if index else ""
        lines.append('std::printf("%s\\\"%s\\\":{\\\"done\\\":%%s,\\\"busy\\\":%%s,\\\"aborted\\\":%%s,\\\"error\\\":%%s,\\\"comm_error\\\":%%d,\\\"oper_error\\\":%%d}",%s.done()?"true":"false",%s.busy()?"true":"false",%s.aborted()?"true":"false",%s.error()?"true":"false",(int)%s.comm_error(),(int)%s.oper_error());' % (prefix, name, name, name, name, name, name, name))
    watch = sorted({int(i) for i in request.get("observe_words", request.get("initial_words", {}))})
    lines.append('std::printf("},\\\"words\\\":{");')
    for position, index in enumerate(watch):
        lines.append('std::printf("%s\\\"%d\\\":%%u",(unsigned)plc::detail::words[%d]);' % ("," if position else "", index, index))
    lines.append('std::printf("},\\\"poison\\\":{");')
    for position, index in enumerate(watch):
        lines.append('std::printf("%s\\\"%d\\\":%%u",(unsigned)plc::detail::indeterminate_words[%d]);' % ("," if position else "", index, index))
    lines.append('std::printf("},\\\"cancel_count\\\":%u,\\\"flags\\\":{\\\"S18\\\":%s,\\\"S17\\\":%s,\\\"SW17\\\":%u},\\\"configured_index_data\\\":{",natal_raw_primary.cancels+natal_raw_alternate.cancels,plc::system(18)?"true":"false",plc::system(17)?"true":"false",(unsigned)(unsigned short)plc::read_system_word(17));')
    for index, (name, config) in enumerate(blocks.items()):
        field = "IndexDataIn" if config.get("kind") == "WRITE_READ_VAR" else "IndexData"
        lines.append('std::printf("%s\\\"%s\\\":%%u",(unsigned)(unsigned short)%s.property(plc::CommProperty::%s));' % ("," if index else "", name, name, field))
    lines.append('std::printf("},\\\"known_words\\\":{");')
    for position, index in enumerate(request.get("probe_known_words", [])):
        lines.append('std::printf("%s\\\"%d\\\":%%u",(unsigned)(unsigned short)plc::read_word(%d));' % ("," if position else "", index, index))
    lines.append('std::printf("},\\\"snapshots\\\":[");for(unsigned i=0;i<snapshots.size();++i){if(i)std::putchar(44);const auto& s=snapshots[i];std::printf("{\\\"block\\\":\\\"%s\\\",\\\"done\\\":%s,\\\"busy\\\":%s,\\\"aborted\\\":%s,\\\"error\\\":%s,\\\"comm_error\\\":%d,\\\"oper_error\\\":%d}",s.name,s.done?"true":"false",s.busy?"true":"false",s.aborted?"true":"false",s.error?"true":"false",s.comm,s.oper);}std::printf("]}\\n");return 0;}')
    return "\n".join(lines) + "\n"


def run_sequence(*, request, repo, work):
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if not compiler:
        raise AssertionError("clang++ missing; never a skip")
    work, repo = Path(work), Path(repo)
    work.mkdir(parents=True, exist_ok=True)
    source, binary = work / "raw-pdu-host.cpp", work / "raw-pdu-host"
    source.write_text(_source(request))
    command = [compiler, "-std=c++17", "-O0", "-I", str(repo / "sdk"), str(source), "-o", str(binary)]
    built = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (work / "compile.json").write_text(json.dumps({"command": command, "returncode": built.returncode, "stderr": built.stderr}, indent=2))
    if built.returncode:
        raise AssertionError("SDK raw-PDU host compilation failed:\n" + built.stderr)
    ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
    (work / "run.json").write_text(json.dumps({"returncode": ran.returncode, "stdout": ran.stdout, "stderr": ran.stderr}, indent=2))
    if ran.returncode:
        raise SDKExecutionError(ran)
    return json.loads(ran.stdout)


def modbus_async(*, engine, request, repo, work):
    if engine == "vm":
        from .host_adapters import modbus_async as original_vm_binding
        return original_vm_binding(engine=engine, request=request, repo=repo, work=work)
    if engine != "sdk":
        raise ValueError("Unknown G11 async backend")
    if request["scenario"] not in ("busy_config_snapshot", "abort_late_response"):
        raise ValueError("Unbound original G11 async scenario")
    events = []
    for position, event in enumerate(request["events"]):
        item = {"now_ms": position * 10, "calls": [{"block": "read", "execute": event.get("execute", False), "abort": event.get("abort", False)}]}
        if "set_property" in event:
            item["set_properties"] = [["read", field, value] for field, value in event["set_property"].items()]
        incoming = event.get("transport_response_hex", event.get("late_response_hex"))
        if incoming is not None:
            item["poll"] = {"kind": "response", "hex": incoming}
        events.append(item)
    observed = run_sequence(request={"blocks": {"read": copy.deepcopy(request["config"])}, "initial_words": copy.deepcopy(request["initial_words"]), "events": events}, repo=repo, work=work)
    status = observed["statuses"]["read"]
    result = {"words": observed["words"], "done": status["done"]}
    if request["scenario"] == "busy_config_snapshot":
        result.update(request_hex=observed["request_hexes"][0], error=status["error"], configured_index_data=observed["configured_index_data"]["read"])
    else:
        result["aborted"] = status["aborted"]
    return result
