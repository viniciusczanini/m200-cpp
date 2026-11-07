#pragma once
// Included inside namespace plc, only under PLC_NATIVE, after communication
// config/result declarations. Local scan-driven PDU model: no sockets or wall
// clock. Policies mirror m200/modbus.py; they are not native PLC timing proof.
namespace detail {
using ModbusToken = unsigned long long;
enum class ModbusPollKind { Pending, Response, BroadcastComplete, Error };
struct ModbusStartResult {
    bool accepted=false;
    ModbusToken token=0;
    i16 comm_error=255;
    i32 oper_error=6;
};
struct ModbusPollResult {
    ModbusPollKind kind=ModbusPollKind::Pending;
    unsigned size=0;
    i16 comm_error=255;
    i32 oper_error=6;
};
struct ModbusTransport {
    void* context=nullptr;
    ModbusStartResult (*start)(void*,const CommunicationConfig&,const unsigned char*,unsigned,unsigned long long)=nullptr;
    ModbusPollResult (*poll)(void*,ModbusToken,unsigned long long,unsigned char*,unsigned)=nullptr;
    void (*cancel)(void*,ModbusToken)=nullptr;
};
inline ModbusTransport modbus_transport{};
// Real embedded link count and Modbus PDU maximum, not PLC word reservations.
inline const void* modbus_link_owners[2]={};
inline unsigned long long modbus_last_ms=0;
inline constexpr unsigned modbus_pdu_capacity=253;
inline constexpr unsigned modbus_read_words=125;

inline bool modbus_transport_installed() {
    return modbus_transport.context || modbus_transport.start ||
           modbus_transport.poll || modbus_transport.cancel;
}
inline bool modbus_transport_ready(const ModbusTransport& transport) {
    return transport.start && transport.poll && transport.cancel;
}
inline void modbus_clock(unsigned long long now) {
    if(now<modbus_last_ms)__builtin_trap();
    modbus_last_ms=now;
}
inline bool modbus_parameters_valid(const CommunicationConfig& c) {
    if(c.kind<0||c.kind>2||(c.link!=1&&c.link!=2)||c.timeout<0)return false;
    int minimum=c.kind==1&&c.link==1?0:1;
    if(c.id<minimum||c.id>(c.link==1?247:16))return false;
    if(c.obj<0||c.obj>5||c.first<0||c.first>65535||c.index<0||c.index>7999)return false;
    if(c.quantity<0||c.quantity>65535||c.first_read<0||c.first_read>65535||
       c.read_quantity<1||c.read_quantity>125||c.index_in<0||c.index_in>7999)return false;
    int count=c.quantity,words=count;
    if(c.kind==0) {
        if(c.obj>3||count<1||count>((c.obj==1||c.obj==2)?2000:125))return false;
        if(c.obj==1||c.obj==2)words=(count+15)/16;
    } else if(c.kind==1) {
        if(c.obj==4||c.obj==5){count=1;words=1;}
        else {
            if((c.obj!=0&&c.obj!=2)||count<1||count>(c.obj==2?1968:123))return false;
            if(c.obj==2)words=(count+15)/16;
        }
    } else {
        if(c.obj!=0||count<1||count>121||c.first_read+c.read_quantity>65536||
           c.index_in+c.read_quantity>8000)return false;
    }
    if(c.kind!=2&&(c.first_read!=0||c.read_quantity!=1||c.index_in!=0))return false;
    return c.first+count<=65536&&c.index+words<=8000;
}
inline unsigned modbus_function(const CommunicationConfig& c) {
    if(c.kind==2)return 23;
    if(c.kind==0) {
        const unsigned functions[4]={3,2,1,4};return functions[c.obj];
    }
    return c.obj==0?16:c.obj==2?15:c.obj==4?5:6;
}
inline void modbus_put_word(unsigned char* out,unsigned value) {
    out[0]=(unsigned char)(value>>8);out[1]=(unsigned char)value;
}
inline unsigned short modbus_get_word(const unsigned char* data) {
    return (unsigned short)(((unsigned)data[0]<<8)|data[1]);
}
inline unsigned short modbus_load_word(const unsigned short* image,unsigned index) {
    // Outgoing global-image data obeys G02's known-word barrier. No request is
    // submitted (or link claimed) if reading an indeterminate source traps.
    return image==::plc::detail::words
        ?(unsigned short)::plc::read_word((int)index):image[index];
}
inline void modbus_store_word(unsigned short* image,unsigned index,unsigned short value) {
    // Only validated receive words recover their own masks. The ordinary word
    // store neither clears arithmetic flags nor touches unrelated cells.
    if(image==::plc::detail::words)
        ::plc::write_word((int)index,::plc::detail::bits_i16(value));
    else image[index]=value;
}
inline unsigned modbus_encode(const CommunicationConfig& c,const unsigned short* words,unsigned char* out) {
    // Caller validates all config/buffer spans before reading the shared image.
    unsigned fc=modbus_function(c);out[0]=(unsigned char)fc;
    if(c.kind==0) {
        modbus_put_word(out+1,(unsigned)c.first);
        modbus_put_word(out+3,(unsigned)c.quantity);return 5;
    }
    if(fc==5||fc==6) {
        modbus_put_word(out+1,(unsigned)c.first);
        modbus_put_word(out+3,fc==5?((modbus_load_word(words,(unsigned)c.index)&1)?0xff00U:0U):modbus_load_word(words,(unsigned)c.index));return 5;
    }
    if(fc==15) {
        unsigned bytes=((unsigned)c.quantity+7)/8;
        modbus_put_word(out+1,(unsigned)c.first);
        modbus_put_word(out+3,(unsigned)c.quantity);out[5]=(unsigned char)bytes;
        for(unsigned i=0;i<bytes;++i)
            out[6+i]=(unsigned char)(modbus_load_word(words,(unsigned)c.index+i/2)>>((i%2)*8));
        if(c.quantity%8)out[5+bytes]&=(unsigned char)((1U<<(c.quantity%8))-1);
        return 6+bytes;
    }
    unsigned header=6;
    if(fc==23) {
        modbus_put_word(out+1,(unsigned)c.first_read);
        modbus_put_word(out+3,(unsigned)c.read_quantity);
        modbus_put_word(out+5,(unsigned)c.first);
        modbus_put_word(out+7,(unsigned)c.quantity);
        out[9]=(unsigned char)(c.quantity*2);header=10;
    } else {
        modbus_put_word(out+1,(unsigned)c.first);
        modbus_put_word(out+3,(unsigned)c.quantity);out[5]=(unsigned char)(c.quantity*2);
    }
    for(int i=0;i<c.quantity;++i)modbus_put_word(out+header+2*(unsigned)i,modbus_load_word(words,(unsigned)(c.index+i)));
    return header+2*(unsigned)c.quantity;
}
inline bool modbus_exception(unsigned code) {
    return code==1||code==2||code==3||code==4||code==5||code==6||code==8||code==10||code==11;
}
inline CommunicationResult modbus_error(i16 comm,i32 oper=0) {
    CommunicationResult result{};result.error=true;result.comm_error=comm;result.oper_error=oper;return result;
}
inline CommunicationResult modbus_transport_error(i16 comm,i32 oper) {
    // A malformed transport error must not masquerade as a valid FB result.
    return comm<0||comm>255?modbus_error(0,2):modbus_error(comm,oper);
}

struct ModbusExecution {
    bool active=false;
    CommunicationConfig config{};
    ModbusTransport transport{};
    ModbusToken token=0;
    unsigned long long started_ms=0;
    unsigned short* destination=nullptr;
    unsigned char request[modbus_pdu_capacity]={};
    unsigned request_size=0;
};
inline void modbus_release(ModbusExecution& active,const void* owner,bool cancel) {
    if(!active.active)return;
    // Retire before calling out: no future invocation polls this token or uses
    // this destination. A late response cannot reach an application write.
    ModbusTransport transport=active.transport;
    ModbusToken token=active.token;
    int link=active.config.link;
    active.active=false;active.destination=nullptr;active.token=0;
    if(modbus_link_owners[link-1]==owner)modbus_link_owners[link-1]=nullptr;
    if(cancel)transport.cancel(transport.context,token);
}
inline CommunicationResult modbus_decode(ModbusExecution& active,const unsigned char* response,unsigned size) {
    unsigned fc=active.request[0];
    if(size<1||size>modbus_pdu_capacity)return modbus_error(0,2);
    if(response[0]==(fc|0x80U)) {
        if(size!=2||!modbus_exception(response[1]))return modbus_error(0,2);
        return modbus_error(254,(i32)response[1]);
    }
    if(response[0]!=fc)return modbus_error(0,2);
    if(fc==5||fc==6||fc==15||fc==16) {
        if(size!=5)return modbus_error(0,2);
        for(unsigned i=0;i<5;++i)if(response[i]!=active.request[i])return modbus_error(0,2);
    } else {
        const CommunicationConfig& c=active.config;
        unsigned count=(unsigned)(fc==23?c.read_quantity:c.quantity);
        bool bits=fc==1||fc==2;
        unsigned bytes=bits?(count+7)/8:count*2;
        if(size!=bytes+2||response[1]!=bytes)return modbus_error(0,2);
        if(bits&&count%8&&(response[size-1]>>(count%8)))return modbus_error(0,2);
        // Decode fully into bounded private staging before the first MW write.
        unsigned short staged[modbus_read_words]={};
        unsigned words=bits?(count+15)/16:count;
        if(words>modbus_read_words)return modbus_error(0,2);
        if(bits) {
            for(unsigned i=0;i<bytes;++i)
                staged[i/2]|=(unsigned short)((unsigned)response[2+i]<<((i%2)*8));
        } else {
            for(unsigned i=0;i<words;++i)staged[i]=modbus_get_word(response+2+2*i);
        }
        unsigned index=(unsigned)(fc==23?c.index_in:c.index);
        for(unsigned i=0;i<words;++i)modbus_store_word(active.destination,index+i,staged[i]);
    }
    CommunicationResult result{};result.done=true;return result;
}
inline CommunicationResult modbus_update(ModbusExecution& active,const void* owner,
        const CommunicationConfig& configured,CommunicationResult state,
        bool execute,bool execute_edge,bool abort_edge,unsigned long long now,unsigned short* words) {
    if(!active.active&&!execute)state={};
    if(active.active) {
        if(abort_edge) {
            modbus_release(active,owner,true);
            state={};state.aborted=true;state.comm_error=2;return state;
        }
        if(active.config.timeout&&now-active.started_ms>=(unsigned long long)active.config.timeout*100ULL) {
            modbus_release(active,owner,true);return modbus_error(1);
        }
        unsigned char response[modbus_pdu_capacity]={};
        ModbusPollResult polled=active.transport.poll(active.transport.context,active.token,now,response,modbus_pdu_capacity);
        if(polled.kind==ModbusPollKind::Pending)return state;
        if(polled.kind==ModbusPollKind::Error) {
            modbus_release(active,owner,true);
            return modbus_transport_error(polled.comm_error,polled.oper_error);
        }
        bool broadcast=active.config.link==1&&active.config.id==0;
        if(broadcast) {
            if(polled.kind!=ModbusPollKind::BroadcastComplete||polled.size!=0)state=modbus_error(0,2);
            else {state={};state.done=true;}
        } else if(polled.kind==ModbusPollKind::Response) {
            state=modbus_decode(active,response,polled.size);
        } else state=modbus_error(0,2);
        modbus_release(active,owner,state.error);
        return state; // Execute edges while Busy never schedule another request.
    }
    if(!execute_edge||abort_edge)return state;
    if(!modbus_parameters_valid(configured))return modbus_error(6);
    int link=configured.link-1;
    if(modbus_link_owners[link])return modbus_error(255,11);
    if(!modbus_transport_ready(modbus_transport))return modbus_error(255,15);
    active.config=configured;
    active.transport=modbus_transport;
    active.destination=words;
    active.started_ms=now;
    active.request_size=modbus_encode(active.config,words,active.request);
    // Reserve before calling the transport, so start cannot expose a free link.
    modbus_link_owners[link]=owner;
    ModbusStartResult started=active.transport.start(active.transport.context,
        active.config,active.request,active.request_size,now);
    if(!started.accepted) {
        modbus_link_owners[link]=nullptr;active.destination=nullptr;
        return modbus_transport_error(started.comm_error,started.oper_error);
    }
    active.token=started.token;active.active=true;
    state={};state.busy=true;return state;
}
} // namespace detail
