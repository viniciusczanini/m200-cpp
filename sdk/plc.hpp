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
inline bool shift_carry=false, arithmetic_error=false;
inline int word_memory_limit = 0;
inline int bit_memory_limit = 0;
inline int timer_next_index = 0;
inline bool previous_inputs[24]={}, previous_memory[1024]={};
inline bool input_rise[24]={}, input_fall[24]={}, memory_rise[1024]={}, memory_fall[1024]={};
inline void begin_scan(){
    for(int i=0;i<24;++i){input_rise[i]=inputs[i]&&!previous_inputs[i];input_fall[i]=previous_inputs[i]&&!inputs[i];previous_inputs[i]=inputs[i];}
    for(int i=0;i<1024;++i){memory_rise[i]=memory[i]&&!previous_memory[i];memory_fall[i]=previous_memory[i]&&!memory[i];previous_memory[i]=memory[i];}
}
inline bool timer_used[255] = {};
inline int claim_timer(int index){if(index<0||index>=255||timer_used[index])__builtin_trap();timer_used[index]=true;if(timer_next_index<=index)timer_next_index=index+1;return index;}
}
inline bool input(int n) { return detail::inputs[n]; }
inline void output(int n, bool v) { detail::outputs[n] = v; }
inline bool output_state(int n) { return detail::outputs[n]; }
inline bool read_m(int n) { return detail::memory[n]; }
inline bool input_rising(int n){if(n<0||n>=24)__builtin_trap();return detail::input_rise[n];}
inline bool input_falling(int n){if(n<0||n>=24)__builtin_trap();return detail::input_fall[n];}
inline bool m_rising(int n){if(n<0||n>=(detail::bit_memory_limit?detail::bit_memory_limit:1024))__builtin_trap();return detail::memory_rise[n];}
inline bool m_falling(int n){if(n<0||n>=(detail::bit_memory_limit?detail::bit_memory_limit:1024))__builtin_trap();return detail::memory_fall[n];}
namespace detail {inline bool rising_history[255]={},falling_history[255]={};}
inline bool rising(int n,bool value){if(n<0||n>=255)__builtin_trap();bool result=value&&!detail::rising_history[n];detail::rising_history[n]=value;return result;}
inline bool falling(int n,bool value){if(n<0||n>=255)__builtin_trap();bool result=detail::falling_history[n]&&!value;detail::falling_history[n]=value;return result;}
inline void write_m(int n,bool v) { detail::memory[n] = v; }
struct BitMemory { explicit BitMemory(int count){if(count<1||count>1024)__builtin_trap();detail::bit_memory_limit=count;} };
inline bool system(int n) {
    if(n==13) return detail::first_scan;
    if(n==20) return detail::index_error;
    if(n==17) return detail::shift_carry;
    if(n==18) return detail::arithmetic_error;
    unsigned period = n==4?10:n==5?100:n==6?1000:60000;
    return ((detail::now_ms / (period/2)) & 1) != 0;
}
inline void clear_index_error(){detail::index_error=false;}
inline void clear_shift_carry(){detail::shift_carry=false;}
inline void clear_arithmetic_error(){detail::arithmetic_error=false;}
inline bool clock_ms(unsigned period) {
    return ((detail::now_ms / (period/2)) & 1) != 0;
}
namespace detail { inline int sr_depth=0; inline bool sr_used[64]={}; }
class Subroutine {
    int index; void (*body)(); const char* metadata_name=nullptr; int metadata_section=-1;
public:
    Subroutine(int n,void (*f)()):index(n),body(f){if(n<0||n>=64||!f||detail::sr_used[n])__builtin_trap();detail::sr_used[n]=true;}
    Subroutine(int n,void (*f)(),const char* name,int section):Subroutine(n,f){if(!name||!*name||section<0)__builtin_trap();metadata_name=name;metadata_section=section;}
    Subroutine(const Subroutine&)=delete;
    Subroutine& operator=(const Subroutine&)=delete;
    void call(bool enable){if(!enable)return;if(detail::sr_depth)__builtin_trap();++detail::sr_depth;body();--detail::sr_depth;}
};
class TimerState {
    int kind, base=1, configured=0, active=0, current=0;
    bool previous=false, result=false, retain=false, dynamic=false, completed=false;
    long long started=-1;
    unsigned long long counted=0;
    void finish(){completed=true;result=kind==0;if(kind!=0)started=-1;}
    void begin(){
        started=(long long)detail::now_ms;active=configured;counted=0;completed=false;
        if(!retain)current=0;
        if(current>=active)finish();
    }
    void refresh(){
        if(started>=0&&!completed){
            unsigned long long ticks=(detail::now_ms-(unsigned long long)started)/(unsigned)base;
            if(ticks>counted){
                if(dynamic)active=configured;
                unsigned long long delta=ticks-counted;
                if(current<active)current+=(int)(delta>(unsigned)(active-current)?(unsigned)(active-current):delta);
                counted=ticks;
                if(current>=active)finish();
            }
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
    TimerState(int index,int tb,int ticks,int k,bool ret=false,bool dyn=false):kind(k),base(tb),configured(ticks),active(ticks),retain(ret),dynamic(dyn){
        detail::claim_timer(index);
        if((tb!=1&&tb!=10&&tb!=100&&tb!=1000&&tb!=60000)||(tb==1&&index>=6)||ticks<0||ticks>9999||(k==2&&ret))__builtin_trap();
    }
    i16 preset()const{return (i16)configured;}
    i16 value(){refresh();return (i16)current;}
    bool done(){refresh();return result;}
    void set_preset(i16 ticks){
        if(ticks<0||ticks>9999)__builtin_trap();refresh();configured=ticks;
        bool paused=kind==0?!previous:previous;
        if(retain&&dynamic&&started<0&&paused&&ticks<current)current=0;
    }
    bool update(bool enabled){
        refresh();
        if(kind==0){
            if(!enabled){if(!retain||completed)current=0;started=-1;result=false;completed=false;}
            else if(started<0)begin();
        }else if(kind==1){
            if(enabled){if(!retain||completed)current=0;started=-1;result=true;completed=false;}
            else if(previous)begin();
        }else if(enabled&&!previous&&started<0){result=true;begin();}
        previous=enabled;refresh();return result;
    }
};
struct Ton:TimerState{explicit Ton(unsigned ms):TimerState(ms,0){} Ton(int i,int b,int p):TimerState(i,b,p,0){} Ton(int i,int b,int p,bool r,bool d):TimerState(i,b,p,0,r,d){}};
struct Tof:TimerState{explicit Tof(unsigned ms):TimerState(ms,1){} Tof(int i,int b,int p):TimerState(i,b,p,1){} Tof(int i,int b,int p,bool r,bool d):TimerState(i,b,p,1,r,d){}};
struct Pulse:TimerState{explicit Pulse(unsigned ms):TimerState(ms,2){} Pulse(int i,int b,int p):TimerState(i,b,p,2){} Pulse(int i,int b,int p,bool r,bool d):TimerState(i,b,p,2,r,d){}};
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
namespace detail {inline bool counter_used[255]={};}
class Counter {
    int configured,current=0;
    bool r=false,s=false,up=false,down=false,e=false,d=false,f=false;
    void apply(int pin,bool enabled){
        bool edge=false;
        if(pin==0)r=enabled;
        else if(pin==1)s=enabled;
        else if(pin==2){edge=enabled&&!up;up=enabled;}
        else {edge=enabled&&!down;down=enabled;}
        if(r){current=0;e=d=f=false;}
        else if(s){current=configured;d=true;}
        else if(pin>=2&&enabled){
            if(edge&&pin==2){current=(current+1)%10000;f=current==0;}
            else if(edge){current=(current+9999)%10000;e=current==9999;}
            d=current==configured;
        }
    }
public:
    // Local policy: see COUNTERS.md; flags/interactions await hardware proof.
    Counter(int index,int preset):configured(preset){
        if(index<0||index>=255||detail::counter_used[index]||preset<0||preset>9999)__builtin_trap();
        detail::counter_used[index]=true;
    }
    i16 preset()const{return (i16)configured;}
    i16 value()const{return (i16)current;}
    bool empty()const{return e;} bool done()const{return d;} bool full()const{return f;}
    void set_preset(i16 value){if(value<0||value>9999)__builtin_trap();configured=value;}
    void reset(bool value){apply(0,value);} void set(bool value){apply(1,value);}
    void count_up(bool value){apply(2,value);} void count_down(bool value){apply(3,value);}
    bool update(bool reset_value,bool set_value,bool up_value,bool down_value){
        reset(reset_value);set(set_value);count_up(up_value);count_down(down_value);return d;
    }
};
struct FallingEdge { bool old=false; bool update(bool v){bool q=!v&&old;old=v;return q;} };
#else
bool input(int);
void output(int,bool);
bool output_state(int);
bool read_m(int);
bool input_rising(int);
bool input_falling(int);
bool m_rising(int);
bool m_falling(int);
bool rising(int,bool);
bool falling(int,bool);
void write_m(int,bool);
struct BitMemory { explicit BitMemory(int); };
bool read_m_indexed(int,int);
void write_m_indexed(int,int,bool);
bool system(int);
void clear_index_error();
void clear_shift_carry();
void clear_arithmetic_error();
bool clock_ms(unsigned);
struct Ton { explicit Ton(unsigned); Ton(int,int,int); Ton(int,int,int,bool,bool); bool update(bool); i16 preset()const; i16 value(); bool done(); void set_preset(i16); };
struct Counter { Counter(int,int); i16 preset()const; i16 value()const; bool empty()const; bool done()const; bool full()const; void set_preset(i16); void reset(bool); void set(bool); void count_up(bool); void count_down(bool); bool update(bool,bool,bool,bool); };
struct Tof { explicit Tof(unsigned); Tof(int,int,int); Tof(int,int,int,bool,bool); bool update(bool); i16 preset()const; i16 value(); bool done(); void set_preset(i16); };
struct Pulse { explicit Pulse(unsigned); Pulse(int,int,int); Pulse(int,int,int,bool,bool); bool update(bool); i16 preset()const; i16 value(); bool done(); void set_preset(i16); };
struct Clock { explicit Clock(unsigned); bool update(bool); };
struct RisingEdge { RisingEdge(); bool update(bool); };
struct FallingEdge { FallingEdge(); bool update(bool); };
#endif
// Fixed-width numeric API. Explicit operations avoid C++ integer promotions.
#ifdef PLC_NATIVE
static_assert(sizeof(i16)==2 && sizeof(i32)==4 && sizeof(f32)==4,"PLC numeric width mismatch");
namespace detail {
inline unsigned short words[8000] = {};
inline i16 bits_i16(unsigned v){unsigned short raw=(unsigned short)v;i16 out;__builtin_memcpy(&out,&raw,2);return out;}
inline i32 bits_i32(unsigned v){i32 out;__builtin_memcpy(&out,&v,4);return out;}
inline i16 check_i16(long long v){if(v < -32768LL || v > 32767LL)arithmetic_error=true;return bits_i16((unsigned)v);}
inline i32 check_i32(long long v){if(v < -2147483648LL || v > 2147483647LL)arithmetic_error=true;return bits_i32((unsigned)v);}
inline f32 check_f32(f32 v){if(!__builtin_isfinite(v))__builtin_trap();return v;}
inline void record_shift(unsigned long long value,int width,int distance,bool left){shift_carry=((value>>(left?width-distance:distance-1))&1U)!=0;}
}
inline i16 read_word(int n){return detail::bits_i16(detail::words[n]);}
inline void write_word(int n,i16 v){detail::words[n]=(unsigned short)v;}
inline bool read_word_bit(int n,int bit){
    if(n<0||n>=(detail::word_memory_limit?detail::word_memory_limit:8000)||bit<0||bit>=16)__builtin_trap();
    return (detail::words[n]&(1U<<bit))!=0;
}
inline void write_word_bit(int n,int bit,bool value){
    if(n<0||n>=(detail::word_memory_limit?detail::word_memory_limit:8000)||bit<0||bit>=16)__builtin_trap();
    unsigned mask=1U<<bit;
    detail::words[n]=(unsigned short)((detail::words[n]&~mask)|(value?mask:0U));
}
namespace detail {
inline void check_bit_region(int bank,int first,int count,int width){
    int limit=bank==0?(bit_memory_limit?bit_memory_limit:1024):bank==1?24:16;
    if(first<0||first%8||count<1||count>width||count>32||first>limit-count)__builtin_trap();
}
inline unsigned read_bits(int bank,int first,int count,int width){
    check_bit_region(bank,first,count,width);unsigned result=0;
    const bool* source=bank==0?memory:bank==1?inputs:outputs;
    for(int bit=0;bit<count;++bit)if(source[first+bit])result|=1U<<bit;
    return result;
}
inline void write_bits(int bank,int first,int count,int width,unsigned value){
    check_bit_region(bank,first,count,width);
    bool* dest=bank==0?memory:outputs;
    for(int bit=0;bit<count;++bit)dest[first+bit]=((value>>bit)&1U)!=0;
}
}
inline i16 read_m_bits_i16(int first,int count){return detail::bits_i16(detail::read_bits(0,first,count,16));}
inline i32 read_m_bits_i32(int first,int count){return detail::bits_i32(detail::read_bits(0,first,count,32));}
inline i16 read_input_bits_i16(int first,int count){return detail::bits_i16(detail::read_bits(1,first,count,16));}
inline i32 read_input_bits_i32(int first,int count){return detail::bits_i32(detail::read_bits(1,first,count,32));}
inline i16 read_output_bits_i16(int first,int count){return detail::bits_i16(detail::read_bits(2,first,count,16));}
inline i32 read_output_bits_i32(int first,int count){return detail::bits_i32(detail::read_bits(2,first,count,32));}
inline void write_m_bits_i16(int first,int count,i16 value){detail::write_bits(0,first,count,16,(unsigned)value);}
inline void write_m_bits_i32(int first,int count,i32 value){detail::write_bits(0,first,count,32,(unsigned)value);}
inline void write_output_bits_i16(int first,int count,i16 value){detail::write_bits(2,first,count,16,(unsigned)value);}
inline void write_output_bits_i32(int first,int count,i32 value){detail::write_bits(2,first,count,32,(unsigned)value);}
inline void copy_m_bits(int dest,int source,int count){
    unsigned snapshot=detail::read_bits(0,source,count,32);
    detail::write_bits(0,dest,count,32,snapshot);
}
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
inline i16 div_i16(i16 a, i16 b){if(b==0){detail::arithmetic_error=true;__builtin_trap();}return detail::check_i16((long long)a/(long long)b);}
inline i16 sqrt_i16(i16 a){if(a<0){detail::arithmetic_error=true;__builtin_trap();}return detail::check_i16((long long)__builtin_sqrt((double)a));}
inline i32 add_i32(i32 a, i32 b){return detail::check_i32((long long)a+(long long)b);}
inline i32 sub_i32(i32 a, i32 b){return detail::check_i32((long long)a-(long long)b);}
inline i32 mul_i32(i32 a, i32 b){return detail::check_i32((long long)a*(long long)b);}
inline i32 div_i32(i32 a, i32 b){if(b==0){detail::arithmetic_error=true;__builtin_trap();}return detail::check_i32((long long)a/(long long)b);}
inline i32 sqrt_i32(i32 a){if(a<0){detail::arithmetic_error=true;__builtin_trap();}return detail::check_i32((long long)__builtin_sqrt((double)a));}
inline f32 add_f32(f32 a, f32 b){return detail::check_f32(a+b);}
inline f32 sub_f32(f32 a, f32 b){return detail::check_f32(a-b);}
inline f32 mul_f32(f32 a, f32 b){return detail::check_f32(a*b);}
inline f32 div_f32(f32 a, f32 b){if(b==0)__builtin_trap();return detail::check_f32(a/b);}
inline f32 sqrt_f32(f32 a){if(a<0)__builtin_trap();return detail::check_f32(__builtin_sqrtf(a));}
inline i16 rem_i16(i16 a, i16 b){if(b==0){detail::arithmetic_error=true;__builtin_trap();}detail::check_i16((long long)a/(long long)b);return detail::check_i16((long long)a%(long long)b);}
inline i16 shl_i16(i16 a, int b){if(b<1||b>16)__builtin_trap();unsigned long long u=(unsigned)a&65535U;detail::record_shift(u,16,b,true);return detail::bits_i16((unsigned)(u<<b));}
inline i16 shr_i16(i16 a, int b){if(b<1||b>16)__builtin_trap();unsigned long long u=(unsigned)a&65535U;detail::record_shift(u,16,b,false);return detail::bits_i16((unsigned)(u>>b));}
inline i16 rol_i16(i16 a, int b){if(b<1||b>16)__builtin_trap();unsigned long long u=(unsigned)a&65535U;detail::record_shift(u,16,b,true);return detail::bits_i16((unsigned)((u<<b)|(u>>(16-b))));}
inline i16 ror_i16(i16 a, int b){if(b<1||b>16)__builtin_trap();unsigned long long u=(unsigned)a&65535U;detail::record_shift(u,16,b,false);return detail::bits_i16((unsigned)((u>>b)|(u<<(16-b))));}
inline i32 rem_i32(i32 a, i32 b){if(b==0){detail::arithmetic_error=true;__builtin_trap();}detail::check_i32((long long)a/(long long)b);return detail::check_i32((long long)a%(long long)b);}
inline i32 shl_i32(i32 a, int b){if(b<1||b>32)__builtin_trap();unsigned long long u=(unsigned)a&0xffffffffU;detail::record_shift(u,32,b,true);return detail::bits_i32((unsigned)(u<<b));}
inline i32 shr_i32(i32 a, int b){if(b<1||b>32)__builtin_trap();unsigned long long u=(unsigned)a&0xffffffffU;detail::record_shift(u,32,b,false);return detail::bits_i32((unsigned)(u>>b));}
inline i32 rol_i32(i32 a, int b){if(b<1||b>32)__builtin_trap();unsigned long long u=(unsigned)a&0xffffffffU;detail::record_shift(u,32,b,true);return detail::bits_i32((unsigned)((u<<b)|(u>>(32-b))));}
inline i32 ror_i32(i32 a, int b){if(b<1||b>32)__builtin_trap();unsigned long long u=(unsigned)a&0xffffffffU;detail::record_shift(u,32,b,false);return detail::bits_i32((unsigned)((u>>b)|(u<<(32-b))));}
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
namespace detail {
inline unsigned bcd_decode(unsigned raw,int digits){unsigned result=0,place=1;for(int i=0;i<digits;++i){unsigned digit=raw&15u;if(digit>9u){arithmetic_error=true;__builtin_trap();}result+=digit*place;place*=10u;raw>>=4;}return result;}
inline unsigned bcd_encode(i32 value,int digits){unsigned limit=1;for(int i=0;i<digits;++i)limit*=10u;if(value<0||(unsigned)value>=limit){arithmetic_error=true;__builtin_trap();}unsigned result=0,raw=(unsigned)value;for(int shift=0;shift<digits*4;shift+=4){result|=(raw%10u)<<shift;raw/=10u;}return result;}
}
inline i16 bcd_to_int(i16 a){return (i16)detail::bcd_decode((unsigned short)a,4);}
inline i32 bcd_to_dint(i32 a){return (i32)detail::bcd_decode((unsigned)a,8);}
inline i16 int_to_bcd(i16 a){return detail::bits_i16(detail::bcd_encode(a,4));}
inline i32 dint_to_bcd(i32 a){return detail::bits_i32(detail::bcd_encode(a,8));}
inline i32 concat_words(i16 low,i16 high){return detail::bits_i32((unsigned)(unsigned short)low|((unsigned)(unsigned short)high<<16));}
// Local signed-widening policy; native DWORD negative semantics pending proof.
inline i32 int_to_dint(i16 a){return (i32)a;}
#else
i16 read_word(int);
void write_word(int,i16);
bool read_word_bit(int,int);
void write_word_bit(int,int,bool);
i16 read_m_bits_i16(int,int);
i32 read_m_bits_i32(int,int);
i16 read_input_bits_i16(int,int);
i32 read_input_bits_i32(int,int);
i16 read_output_bits_i16(int,int);
i32 read_output_bits_i32(int,int);
void write_m_bits_i16(int,int,i16);
void write_m_bits_i32(int,int,i32);
void write_output_bits_i16(int,int,i16);
void write_output_bits_i32(int,int,i32);
void copy_m_bits(int,int,int);
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
i16 bcd_to_int(i16);
i32 bcd_to_dint(i32);
i16 int_to_bcd(i16);
i32 dint_to_bcd(i32);
i32 concat_words(i16,i16);
i32 int_to_dint(i16);
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
struct Subroutine { Subroutine(int,void(*)()); Subroutine(int,void(*)(),const char*,int); void call(bool); };
struct ReadVar { ReadVar(Link,int,int,Object,int,int,int); ReadVar(int,Link,int,int,Object,int,int,int); bool update(bool,bool); bool done()const; bool busy()const; bool aborted()const; bool error()const; i16 comm_error()const; i32 oper_error()const; };
struct WriteVar { WriteVar(Link,int,int,Object,int,int,int); WriteVar(int,Link,int,int,Object,int,int,int); bool update(bool,bool); bool done()const; bool busy()const; bool aborted()const; bool error()const; i16 comm_error()const; i32 oper_error()const; };
struct WriteReadVar { WriteReadVar(Link,int,int,int,int,int,int,int,int); WriteReadVar(int,Link,int,int,int,int,int,int,int,int); bool update(bool,bool); bool done()const; bool busy()const; bool aborted()const; bool error()const; i16 comm_error()const; i32 oper_error()const; };
#endif

}
