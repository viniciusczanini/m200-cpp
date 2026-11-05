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
}
