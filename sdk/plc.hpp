#pragma once

// This API is type-checked by Clang; only the documented subset is translated.
namespace plc {
#ifdef PLC_NATIVE
namespace detail {
inline bool inputs[24] = {};
inline bool outputs[16] = {};
inline bool memory[1024] = {};
inline unsigned long long now_ms = 0;
inline bool first_scan = true;
}
inline bool input(int n) { return detail::inputs[n]; }
inline void output(int n, bool v) { detail::outputs[n] = v; }
inline bool output_state(int n) { return detail::outputs[n]; }
inline bool read_m(int n) { return detail::memory[n]; }
inline void write_m(int n,bool v) { detail::memory[n] = v; }
inline bool system(int n) {
    if(n==13) return detail::first_scan;
    unsigned period = n==4?10:n==5?100:n==6?1000:60000;
    return ((detail::now_ms / (period/2)) & 1) != 0;
}
inline bool clock_ms(unsigned period) {
    return ((detail::now_ms / (period/2)) & 1) != 0;
}
class TimerState {
    unsigned duration;
    int kind;
    bool previous = false, running = false, result = false;
    unsigned long long started = 0;
public:
    TimerState(unsigned ms,int k):duration(ms),kind(k){}
    bool update(bool enabled) {
        if(kind==0) {
            if(!enabled){running=false;result=false;}
            else { if(!running){running=true;started=detail::now_ms;} result=detail::now_ms-started>=duration; }
        } else if(kind==1) {
            if(enabled){result=true;running=false;}
            else { if(previous){running=true;started=detail::now_ms;} if(running && detail::now_ms-started>=duration){result=false;running=false;} }
        } else {
            if(enabled&&!previous&&!running){running=true;started=detail::now_ms;}
            if(running&&detail::now_ms-started>=duration)running=false;
            result=running;
        }
        previous=enabled;return result;
    }
};
struct Ton:TimerState{explicit Ton(unsigned ms):TimerState(ms,0){}};
struct Tof:TimerState{explicit Tof(unsigned ms):TimerState(ms,1){}};
struct Pulse:TimerState{explicit Pulse(unsigned ms):TimerState(ms,2){}};
class Clock {
    Ton turn_on, turn_off;
    bool value=false;
public:
    explicit Clock(unsigned half_period_ms):turn_on(half_period_ms),turn_off(half_period_ms){}
    bool update(bool enabled) {
        bool on=turn_on.update(enabled&&!value);
        bool off=turn_off.update(enabled&&value);
        if(!enabled)value=false;
        else if(on)value=true;
        else if(off)value=false;
        return value;
    }
};
struct RisingEdge { bool old=false; bool update(bool v){bool q=v&&!old;old=v;return q;} };
struct FallingEdge { bool old=false; bool update(bool v){bool q=!v&&old;old=v;return q;} };
#else
bool input(int);
void output(int,bool);
bool output_state(int);
bool read_m(int);
void write_m(int,bool);
bool system(int);
bool clock_ms(unsigned);
struct Ton { explicit Ton(unsigned); bool update(bool); };
struct Tof { explicit Tof(unsigned); bool update(bool); };
struct Pulse { explicit Pulse(unsigned); bool update(bool); };
struct Clock { explicit Clock(unsigned); bool update(bool); };
struct RisingEdge { RisingEdge(); bool update(bool); };
struct FallingEdge { FallingEdge(); bool update(bool); };
#endif
// Fixed-width numeric API. Explicit operations avoid C++ integer promotions.
using i16 = short;
using i32 = int;
using f32 = float;
#ifdef PLC_NATIVE
static_assert(sizeof(i16)==2 && sizeof(i32)==4 && sizeof(f32)==4,"PLC numeric width mismatch");
namespace detail {
inline unsigned short words[8000] = {};
inline i16 check_i16(long long v){if(v < -32768LL || v > 32767LL)__builtin_trap();return (i16)v;}
inline i32 check_i32(long long v){if(v < -2147483648LL || v > 2147483647LL)__builtin_trap();return (i32)v;}
inline f32 check_f32(f32 v){if(!__builtin_isfinite(v))__builtin_trap();return v;}
inline i16 bits_i16(unsigned v){unsigned short raw=(unsigned short)v;i16 out;__builtin_memcpy(&out,&raw,2);return out;}
inline i32 bits_i32(unsigned v){i32 out;__builtin_memcpy(&out,&v,4);return out;}
}
inline i16 read_word(int n){return detail::bits_i16(detail::words[n]);}
inline void write_word(int n,i16 v){detail::words[n]=(unsigned short)v;}
inline i32 read_dword(int n){return detail::bits_i32((unsigned)detail::words[n]|((unsigned)detail::words[n+1]<<16));}
inline void write_dword(int n,i32 v){unsigned raw;__builtin_memcpy(&raw,&v,4);detail::words[n]=(unsigned short)raw;detail::words[n+1]=(unsigned short)(raw>>16);}
inline f32 read_real(int n){i32 raw=read_dword(n);f32 out;__builtin_memcpy(&out,&raw,4);return detail::check_f32(out);}
inline void write_real(int n,f32 v){i32 raw;__builtin_memcpy(&raw,&v,4);write_dword(n,raw);}

inline i16 add_i16(i16 a, i16 b){return detail::check_i16((long long)a+(long long)b);}
inline i16 sub_i16(i16 a, i16 b){return detail::check_i16((long long)a-(long long)b);}
inline i16 mul_i16(i16 a, i16 b){return detail::check_i16((long long)a*(long long)b);}
inline i16 div_i16(i16 a, i16 b){if(b==0)__builtin_trap();return detail::check_i16((long long)a/(long long)b);}
inline i16 sqrt_i16(i16 a){if(a<0)__builtin_trap();return detail::check_i16((long long)__builtin_sqrt((double)a));}
inline i32 add_i32(i32 a, i32 b){return detail::check_i32((long long)a+(long long)b);}
inline i32 sub_i32(i32 a, i32 b){return detail::check_i32((long long)a-(long long)b);}
inline i32 mul_i32(i32 a, i32 b){return detail::check_i32((long long)a*(long long)b);}
inline i32 div_i32(i32 a, i32 b){if(b==0)__builtin_trap();return detail::check_i32((long long)a/(long long)b);}
inline i32 sqrt_i32(i32 a){if(a<0)__builtin_trap();return detail::check_i32((long long)__builtin_sqrt((double)a));}
inline f32 add_f32(f32 a, f32 b){return detail::check_f32(a+b);}
inline f32 sub_f32(f32 a, f32 b){return detail::check_f32(a-b);}
inline f32 mul_f32(f32 a, f32 b){return detail::check_f32(a*b);}
inline f32 div_f32(f32 a, f32 b){if(b==0)__builtin_trap();return detail::check_f32(a/b);}
inline f32 sqrt_f32(f32 a){if(a<0)__builtin_trap();return detail::check_f32(__builtin_sqrtf(a));}
inline i16 rem_i16(i16 a, i16 b){if(b==0)__builtin_trap();detail::check_i16((long long)a/(long long)b);return detail::check_i16((long long)a%(long long)b);}
inline i16 shl_i16(i16 a, int b){if(b<1||b>16)__builtin_trap();unsigned long long u=(unsigned)a&65535U;return detail::bits_i16((unsigned)(u<<b));}
inline i16 shr_i16(i16 a, int b){if(b<1||b>16)__builtin_trap();unsigned long long u=(unsigned)a&65535U;return detail::bits_i16((unsigned)(u>>b));}
inline i16 rol_i16(i16 a, int b){if(b<1||b>16)__builtin_trap();unsigned long long u=(unsigned)a&65535U;return detail::bits_i16((unsigned)((u<<b)|(u>>(16-b))));}
inline i16 ror_i16(i16 a, int b){if(b<1||b>16)__builtin_trap();unsigned long long u=(unsigned)a&65535U;return detail::bits_i16((unsigned)((u>>b)|(u<<(16-b))));}
inline i32 rem_i32(i32 a, i32 b){if(b==0)__builtin_trap();detail::check_i32((long long)a/(long long)b);return detail::check_i32((long long)a%(long long)b);}
inline i32 shl_i32(i32 a, int b){if(b<1||b>32)__builtin_trap();unsigned long long u=(unsigned)a&0xffffffffU;return detail::bits_i32((unsigned)(u<<b));}
inline i32 shr_i32(i32 a, int b){if(b<1||b>32)__builtin_trap();unsigned long long u=(unsigned)a&0xffffffffU;return detail::bits_i32((unsigned)(u>>b));}
inline i32 rol_i32(i32 a, int b){if(b<1||b>32)__builtin_trap();unsigned long long u=(unsigned)a&0xffffffffU;return detail::bits_i32((unsigned)((u<<b)|(u>>(32-b))));}
inline i32 ror_i32(i32 a, int b){if(b<1||b>32)__builtin_trap();unsigned long long u=(unsigned)a&0xffffffffU;return detail::bits_i32((unsigned)((u>>b)|(u<<(32-b))));}
inline i16 and_i16(i16 a, i16 b){return detail::bits_i16(a&b);}
inline i16 or_i16(i16 a, i16 b){return detail::bits_i16(a|b);}
inline i16 xor_i16(i16 a, i16 b){return detail::bits_i16(a^b);}
inline i16 not_i16(i16 a){return detail::bits_i16(~a);}
inline i32 abs_i32(i32 a){return detail::check_i32(a<0?-(long long)a:(long long)a);}
inline f32 abs_f32(f32 a){return detail::check_f32(__builtin_fabsf(a));}
inline f32 trunc_f32(f32 a){return detail::check_f32(__builtin_truncf(a));}
inline f32 log_f32(f32 a){return detail::check_f32(__builtin_log10f(a));}
inline f32 ln_f32(f32 a){return detail::check_f32(__builtin_logf(a));}
inline f32 exp_f32(f32 a){return detail::check_f32(__builtin_expf(a));}
inline f32 sin_f32(f32 a){if(a < -12867.963509103793 || a > 12867.963509103793)__builtin_trap();return detail::check_f32(__builtin_sinf(a));}
inline f32 cos_f32(f32 a){if(a < -12867.963509103793 || a > 12867.963509103793)__builtin_trap();return detail::check_f32(__builtin_cosf(a));}
inline f32 tan_f32(f32 a){if(a < -12867.963509103793 || a > 12867.963509103793)__builtin_trap();return detail::check_f32(__builtin_tanf(a));}
inline f32 asin_f32(f32 a){return detail::check_f32(__builtin_asinf(a));}
inline f32 acos_f32(f32 a){return detail::check_f32(__builtin_acosf(a));}
inline f32 atan_f32(f32 a){return detail::check_f32(__builtin_atanf(a));}
inline f32 int_to_real(i16 a){return (f32)a;}
inline f32 dint_to_real(i32 a){return (f32)a;}
inline i16 real_to_int(f32 a){double v=__builtin_rint((double)a);if(!__builtin_isfinite(v)||v<-32768.0||v>32767.0)__builtin_trap();return (i16)v;}
inline i32 real_to_dint(f32 a){double v=__builtin_rint((double)a);if(!__builtin_isfinite(v)||v<-2147483648.0||v>2147483647.0)__builtin_trap();return (i32)v;}
inline i16 low_word(i32 a){return detail::bits_i16((unsigned)a);}
inline i16 high_word(i32 a){return detail::bits_i16((unsigned)a>>16);}
#else
i16 read_word(int);
void write_word(int,i16);
i32 read_dword(int);
void write_dword(int,i32);
f32 read_real(int);
void write_real(int,f32);
i16 add_i16(i16,i16);
i16 sub_i16(i16,i16);
i16 mul_i16(i16,i16);
i16 div_i16(i16,i16);
i16 sqrt_i16(i16);
i32 add_i32(i32,i32);
i32 sub_i32(i32,i32);
i32 mul_i32(i32,i32);
i32 div_i32(i32,i32);
i32 sqrt_i32(i32);
f32 add_f32(f32,f32);
f32 sub_f32(f32,f32);
f32 mul_f32(f32,f32);
f32 div_f32(f32,f32);
f32 sqrt_f32(f32);
i16 rem_i16(i16,i16);
i16 shl_i16(i16,int);
i16 shr_i16(i16,int);
i16 rol_i16(i16,int);
i16 ror_i16(i16,int);
i32 rem_i32(i32,i32);
i32 shl_i32(i32,int);
i32 shr_i32(i32,int);
i32 rol_i32(i32,int);
i32 ror_i32(i32,int);
i16 and_i16(i16,i16);
i16 or_i16(i16,i16);
i16 xor_i16(i16,i16);
i16 not_i16(i16);
i32 abs_i32(i32);
f32 abs_f32(f32);
f32 trunc_f32(f32);
f32 log_f32(f32);
f32 ln_f32(f32);
f32 exp_f32(f32);
f32 sin_f32(f32);
f32 cos_f32(f32);
f32 tan_f32(f32);
f32 asin_f32(f32);
f32 acos_f32(f32);
f32 atan_f32(f32);
f32 int_to_real(i16);
f32 dint_to_real(i32);
i16 real_to_int(f32);
i32 real_to_dint(f32);
i16 low_word(i32);
i16 high_word(i32);
#endif
// Native Modbus function blocks. Ports/endpoints are configured in the template.
enum class Link : int { Serial1=1, Ethernet=2 };
enum class Object : int { HoldingWords=0, DiscreteInputs=1, Coils=2, InputWords=3, SingleCoil=4, SingleRegister=5 };
#ifdef PLC_NATIVE
namespace detail {
struct CommunicationConfig { int kind,link,id,timeout,obj,first,quantity,index,first_read,read_quantity,index_in; };
struct CommunicationResult { bool done=false,busy=false,aborted=false,error=false; i16 comm_error=0; i32 oper_error=0; };
inline int communication_counts[3]={};
// Explicit test transport callback. No device or success is fabricated by default.
inline CommunicationResult (*communication_hook)(const CommunicationConfig&,int,bool,bool,unsigned long long,unsigned short*) = nullptr;
}
class Communication {
    detail::CommunicationConfig config;
    int index;
    detail::CommunicationResult state;
    bool initialized=false,old_execute=false,old_abort=false;
public:
    Communication(int kind,Link link,int id,int timeout,Object obj,int first,int qty,int data,int read_first=0,int read_qty=1,int in_data=0,int native_index=-1)
      :config{kind,(int)link,id,timeout,(int)obj,first,qty,data,read_first,read_qty,in_data},index(native_index<0?detail::communication_counts[kind]++:native_index){if(index<0||index>=32)__builtin_trap();}
    bool update(bool execute,bool abort) {
        if(detail::communication_hook) {
            state=detail::communication_hook(config,index,execute,abort,detail::now_ms,detail::words);
        } else {
            bool edge=initialized && execute && !old_execute;
            bool cancel=initialized && abort && !old_abort;
            if(!execute) state={};
            if(edge&&!cancel){state={};state.error=true;state.comm_error=255;state.oper_error=15;}
        }
        initialized=true;old_execute=execute;old_abort=abort;return state.done;
    }
    bool done() const{return state.done;}
    bool busy() const{return state.busy;}
    bool aborted() const{return state.aborted;}
    bool error() const{return state.error;}
    i16 comm_error() const{return state.comm_error;}
    i32 oper_error() const{return state.oper_error;}
};
struct ReadVar:Communication { ReadVar(Link l,int id,int t,Object o,int f,int q,int d):Communication(0,l,id,t,o,f,q,d){} ReadVar(int n,Link l,int id,int t,Object o,int f,int q,int d):Communication(0,l,id,t,o,f,q,d,0,1,0,n){} };
struct WriteVar:Communication { WriteVar(Link l,int id,int t,Object o,int f,int q,int d):Communication(1,l,id,t,o,f,q,d){} WriteVar(int n,Link l,int id,int t,Object o,int f,int q,int d):Communication(1,l,id,t,o,f,q,d,0,1,0,n){} };
struct WriteReadVar:Communication { WriteReadVar(Link l,int id,int t,int f,int q,int d,int rf,int rq,int rd):Communication(2,l,id,t,Object::HoldingWords,f,q,d,rf,rq,rd){} WriteReadVar(int n,Link l,int id,int t,int f,int q,int d,int rf,int rq,int rd):Communication(2,l,id,t,Object::HoldingWords,f,q,d,rf,rq,rd,n){} };
#else
struct ReadVar { ReadVar(Link,int,int,Object,int,int,int); ReadVar(int,Link,int,int,Object,int,int,int); bool update(bool,bool); bool done()const; bool busy()const; bool aborted()const; bool error()const; i16 comm_error()const; i32 oper_error()const; };
struct WriteVar { WriteVar(Link,int,int,Object,int,int,int); WriteVar(int,Link,int,int,Object,int,int,int); bool update(bool,bool); bool done()const; bool busy()const; bool aborted()const; bool error()const; i16 comm_error()const; i32 oper_error()const; };
struct WriteReadVar { WriteReadVar(Link,int,int,int,int,int,int,int,int); WriteReadVar(int,Link,int,int,int,int,int,int,int,int); bool update(bool,bool); bool done()const; bool busy()const; bool aborted()const; bool error()const; i16 comm_error()const; i32 oper_error()const; };
#endif

}
