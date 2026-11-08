#include <plc.hpp>

// Revoada20, 10 outputs, 600ms/unit; formula + real bounded shift loop.
// No frame table. While-loop position is bounded0..9; output write is packed16.
// I0 START rising; I1 STOP; I2 RESET. STOP/RESET dominate and switch all Q off.
// Two 1ms TON windows preserve sampled overshoot before their 9999ms limit.
// Service this scan at least once per1999ms; saturation latches a dark fault.
// RESET clears fault. A held START never rearms after STOP/RESET.
plc::Ton clock_a{0,1,9999};
plc::Ton clock_b{1,1,9999};
bool running=false;
bool fault=false;
plc::i16 segment=0;
plc::i16 offset=0;

void scan() {
    bool start=plc::input_rising(0);
    bool stop=plc::input(1);
    bool reset=plc::input(2);
    bool halt=stop || reset;
    if(halt) { running=false; segment=0; offset=0; }
    if(reset) { fault=false; }
    if(start && !halt && !running && !fault) {
        running=true; segment=0; offset=0;
    }
    plc::i16 before=clock_a.value();
    if(segment!=0) { before=clock_b.value(); }
    if(running && before>=9999) { fault=true; running=false; }
    if(running && before>=8000) {
        offset=plc::rem_i16(plc::add_i16(offset,before),12000);
        segment=plc::sub_i16(1,segment);
    }
    bool a_done=clock_a.update(running && segment==0);
    bool b_done=clock_b.update(running && segment==1);
    plc::i16 elapsed=0;
    plc::i16 mask=0;
    if(running) {
        plc::i16 sample=clock_a.value();
        if(segment!=0) { sample=clock_b.value(); }
        elapsed=plc::rem_i16(plc::add_i16(offset,sample),12000);
        plc::i16 unit=plc::div_i16(elapsed,600);
        if(unit>10) { unit=plc::sub_i16(21,unit); }
        plc::i16 position=0;
        if(unit>0) { position=plc::sub_i16(unit,1); }
        mask=1;
        plc::i16 cursor=0;
        while(cursor<position) {
            mask=plc::shl_i16(mask,1);
            cursor=plc::add_i16(cursor,1);
        }
    }
    plc::write_output_bits_i16(0,16,mask);
    plc::write_word(180,elapsed);
    plc::write_word(181,mask);
}
