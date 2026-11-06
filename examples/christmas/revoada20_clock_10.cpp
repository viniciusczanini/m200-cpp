#include <plc.hpp>

// Revoada20: real phase/reflection/shift algorithm; no table and no timer.
// I0 START rising, I1 STOP, I2 RESET. STOP/RESET dominate; held START cannot rearm.
// S5 is sampled once; history advances even stopped. Six rises advance one unit.
// First unit500..600ms depends on START/S5 phase; subsequent600ms need every edge.
// No monotonic/missed-edge fault inference. MW180 exposes phase0..19.
bool running=false;
bool previous_clock=false;
plc::i16 beats=0;
plc::i16 phase=0;

void scan() {
    bool sample=plc::clock_ms(100);
    bool clock_rise=sample && !previous_clock;
    previous_clock=sample;
    bool start=plc::input_rising(0);
    bool halt=plc::input(1) || plc::input(2);
    if(halt) { running=false; beats=0; phase=0; }
    else if(start && !running) { running=true; beats=0; phase=0; }
    if(running && clock_rise) {
        beats=plc::add_i16(beats,1);
        if(beats==6) {
            beats=0;
            phase=plc::add_i16(phase,1);
            if(phase==20) { phase=0; }
        }
    }
    plc::i16 mask=0;
    if(running) {
        plc::i16 reflected=phase;
        if(reflected>10) { reflected=plc::sub_i16(21,reflected); }
        plc::i16 position=0;
        if(reflected>0) { position=plc::sub_i16(reflected,1); }
        mask=1;
        plc::i16 cursor=0;
        while(cursor<position) {
            mask=plc::shl_i16(mask,1);
            cursor=plc::add_i16(cursor,1);
        }
    }
    plc::write_output_bits_i16(0,16,mask);
    plc::write_word(180,phase);
}
