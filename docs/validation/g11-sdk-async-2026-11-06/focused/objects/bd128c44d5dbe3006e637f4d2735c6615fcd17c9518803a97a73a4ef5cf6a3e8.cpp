#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#define PLC_NATIVE
#include <plc.hpp>

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

int main(){plc::WordMemory image{8000};Script first,second;
plc::WriteVar block{0,plc::Link::Serial1,1,100,plc::Object::SingleRegister,1,1,100};
plc::detail::modbus_transport={&first,raw_start,raw_poll,raw_cancel};
plc::write_word(100,(plc::i16)(unsigned short)42330);
plc::detail::now_ms=0;
stimulus={};stimulus.kind=ModbusPollKind::Pending;stimulus.bytes={};stimulus.size=0;stimulus.comm=255;stimulus.oper=6;stimulus.accepted=true;
block.update(false,false);
plc::detail::now_ms=10;
stimulus={};stimulus.kind=ModbusPollKind::Pending;stimulus.bytes={};stimulus.size=0;stimulus.comm=255;stimulus.oper=6;stimulus.accepted=true;
block.update(true,false);
plc::detail::now_ms=20;
stimulus={};stimulus.kind=ModbusPollKind::Response;stimulus.bytes={6,0,1,165,90};stimulus.size=5;stimulus.comm=255;stimulus.oper=6;stimulus.accepted=true;
block.update(true,false);
std::printf("{\"request_hexes\":[");for(unsigned i=0;i<recorded.size();++i){if(i)std::putchar(44);std::putchar(34);for(unsigned char b:recorded[i].bytes)std::printf("%02X",(unsigned)b);std::putchar(34);}std::printf("],\"request_ids\":[");
for(unsigned i=0;i<recorded.size();++i){if(i)std::putchar(44);std::printf("%d",recorded[i].id);}std::printf("],\"request_links\":[");for(unsigned i=0;i<recorded.size();++i){if(i)std::putchar(44);std::printf("%d",recorded[i].link);}std::printf("],\"statuses\":{");
std::printf("\"block\":{\"done\":%s,\"busy\":%s,\"aborted\":%s,\"error\":%s,\"comm_error\":%d,\"oper_error\":%d}",block.done()?"true":"false",block.busy()?"true":"false",block.aborted()?"true":"false",block.error()?"true":"false",(int)block.comm_error(),(int)block.oper_error());
std::printf("},\"words\":{");
std::printf("\"100\":%u",(unsigned)plc::detail::words[100]);
std::printf("},\"poison\":{");
std::printf("\"100\":%u",(unsigned)plc::detail::indeterminate_words[100]);
std::printf("},\"cancel_count\":%u,\"flags\":{\"S18\":%s,\"S17\":%s,\"SW17\":%u},\"configured_index_data\":{",first.cancels+second.cancels,plc::system(18)?"true":"false",plc::system(17)?"true":"false",(unsigned)(unsigned short)plc::read_system_word(17));
std::printf("\"block\":%u",(unsigned)(unsigned short)block.property(plc::CommProperty::IndexData));
std::printf("},\"known_words\":{");
std::printf("},\"snapshots\":[");for(unsigned i=0;i<snapshots.size();++i){if(i)std::putchar(44);const auto& s=snapshots[i];std::printf("{\"block\":\"%s\",\"done\":%s,\"busy\":%s,\"aborted\":%s,\"error\":%s,\"comm_error\":%d,\"oper_error\":%d}",s.name,s.done?"true":"false",s.busy?"true":"false",s.aborted?"true":"false",s.error?"true":"false",s.comm,s.oper);}std::printf("]}\n");return 0;}
