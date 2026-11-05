#pragma once

// This API is type-checked by Clang; only the documented subset is translated.
namespace plc {
using i16 = short;
using i32 = int;
using f32 = float;
#ifdef PLC_NATIVE
namespace detail {
inline bool inputs[24] = {};
inline bool outputs[16] = {};
inline bool memory[1024] = {};
inline unsigned long long now_ms = 0;
inline bool first_scan = true;
inline bool index_error = false;
inline int word_memory_limit = 0;
inline int bit_memory_limit = 0;
inline int timer_next_index = 0;
inline bool timer_used[255] = {};
inline int claim_timer(int index){if(index<0||index>=255||timer_used[index])__builtin_trap();timer_used[index]=true;if(timer_next_index<=index)timer_next_index=index+1;return index;}
}
inline bool input(int n) { return detail::inputs[n]; }
inline void output(int n, bool v) { detail::outputs[n] = v; }
inline bool output_state(int n) { return detail::outputs[n]; }
inline bool read_m(int n) { return detail::memory[n]; }
inline void write_m(int n,bool v) { detail::memory[n] = v; }
struct BitMemory { explicit BitMemory(int count){if(count<1||count>1024)__builtin_trap();detail::bit_memory_limit=count;} };
inline bool system(int n) {
    if(n==13) return detail::first_scan;
    if(n==20) return detail::index_error;
    unsigned period = n==4?10:n==5?100:n==6?1000:60000;
    return ((detail::now_ms / (period/2)) & 1) != 0;
}
inline void clear_index_error(){detail::index_error=false;}
inline bool clock_ms(unsigned period) {
    return ((detail::now_ms / (period/2)) & 1) != 0;
}
class TimerState {
    int kind, base=1, configured=0, active=0, current=0;
    bool previous=false, result=false;
    long long started=-1;
    void begin(){started=(long long)detail::now_ms;active=configured;current=0;}
    void refresh(){
        if(started>=0){
            unsigned long long ticks=(detail::now_ms-(unsigned long long)started)/(unsigned)base;
            current=ticks>(unsigned)active?active:(int)ticks;
            if(ticks>=(unsigned)active){result=kind==0;if(kind!=0)started=-1;}
        }
        if(kind==2&&started<0&&!previous)current=0;
    }
public:
    TimerState(unsigned ms,int k):kind(k){
        int index=detail::claim_timer(detail::timer_next_index);
        const int bases[]={1,10,100,1000,60000};
        bool found=false;
        for(int candidate:bases){if(candidate==1&&index>=6)continue;
            if(ms<=(unsigned)candidate*9999U&&ms%(unsigned)candidate==0){base=candidate;configured=(int)(ms/(unsigned)base);found=true;break;}}
        if(!found)__builtin_trap();active=configured;
    }
    TimerState(int index,int tb,int ticks,int k):kind(k),base(tb),configured(ticks),active(ticks){
        detail::claim_timer(index);
        if((tb!=1&&tb!=10&&tb!=100&&tb!=1000&&tb!=60000)||(tb==1&&index>=6)||ticks<0||ticks>9999)__builtin_trap();
    }
    i16 preset()const{return (i16)configured;}
    i16 value(){refresh();return (i16)current;}
    bool done(){refresh();return result;}
    void set_preset(i16 ticks){if(ticks<0||ticks>9999)__builtin_trap();configured=ticks;}
    bool update(bool enabled){
        refresh();
        if(kind==0){if(!enabled){started=-1;current=0;result=false;}else if(started<0)begin();}
        else if(kind==1){if(enabled){started=-1;current=0;result=true;}else if(previous)begin();}
        else if(enabled&&!previous&&started<0){begin();result=true;}
        previous=enabled;refresh();return result;
    }
};
struct Ton:TimerState{explicit Ton(unsigned ms):TimerState(ms,0){} Ton(int i,int b,int p):TimerState(i,b,p,0){}};
struct Tof:TimerState{explicit Tof(unsigned ms):TimerState(ms,1){} Tof(int i,int b,int p):TimerState(i,b,p,1){}};
struct Pulse:TimerState{explicit Pulse(unsigned ms):TimerState(ms,2){} Pulse(int i,int b,int p):TimerState(i,b,p,2){}};
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
struct BitMemory { explicit BitMemory(int); };
bool read_m_indexed(int,int);
void write_m_indexed(int,int,bool);
bool system(int);
void clear_index_error();
bool clock_ms(unsigned);
struct Ton { explicit Ton(unsigned); Ton(int,int,int); bool update(bool); i16 preset()const; i16 value(); bool done(); void set_preset(i16); };
struct Tof { explicit Tof(unsigned); Tof(int,int,int); bool update(bool); i16 preset()const; i16 value(); bool done(); void set_preset(i16); };
struct Pulse { explicit Pulse(unsigned); Pulse(int,int,int); bool update(bool); i16 preset()const; i16 value(); bool done(); void set_preset(i16); };
struct Clock { explicit Clock(unsigned); bool update(bool); };
struct RisingEdge { RisingEdge(); bool update(bool); };
struct FallingEdge { FallingEdge(); bool update(bool); };
#endif
// Fixed-width numeric API. Explicit operations avoid C++ integer promotions.
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
struct WordMemory {
    explicit WordMemory(int count){if(count<1||count>8000)__builtin_trap();detail::word_memory_limit=count;}
};
namespace detail {
inline int indexed_word(int base,int index_word,int width){
    if(word_memory_limit<1||base<0||base+width>word_memory_limit||index_word<0||index_word>=word_memory_limit)__builtin_trap();
    long position=(long)base+(long)read_word(index_word);
    if(position<0||position+width>word_memory_limit){index_error=true;return base;}
    return (int)position;
}
}
inline i16 read_word_indexed(int base,int index_word){return read_word(detail::indexed_word(base,index_word,1));}
inline i32 read_dword_indexed(int base,int index_word){return read_dword(detail::indexed_word(base,index_word,2));}
inline f32 read_real_indexed(int base,int index_word){return read_real(detail::indexed_word(base,index_word,2));}
inline void write_word_indexed(int base,int index_word,i16 v){write_word(detail::indexed_word(base,index_word,1),v);}
inline void write_dword_indexed(int base,int index_word,i32 v){write_dword(detail::indexed_word(base,index_word,2),v);}
inline void write_real_indexed(int base,int index_word,f32 v){write_real(detail::indexed_word(base,index_word,2),v);}
namespace detail {
inline int indexed_bit(int base,int index_word){
    if(bit_memory_limit<1||base<0||base>=bit_memory_limit||word_memory_limit<1||index_word<0||index_word>=word_memory_limit)__builtin_trap();
    long position=(long)base+(long)read_word(index_word);
    if(position<0||position>=bit_memory_limit){index_error=true;return base;}
    return (int)position;
}
}
inline bool read_m_indexed(int base,int index_word){return read_m(detail::indexed_bit(base,index_word));}
inline void write_m_indexed(int base,int index_word,bool value){write_m(detail::indexed_bit(base,index_word),value);}

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
struct WordMemory { explicit WordMemory(int); };
i16 read_word_indexed(int,int);
i32 read_dword_indexed(int,int);
f32 read_real_indexed(int,int);
void write_word_indexed(int,int,i16);
void write_dword_indexed(int,int,i32);
void write_real_indexed(int,int,f32);
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
