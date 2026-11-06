#include <plc.hpp>

// Native configured schedule candidate. Metadata bindings are statically sourced;
// editor open/compile/save/reopen and endpoint timing remain unvalidated.
// index,bank(0=M,1=Q0),output,sd,sm,sh,sn,ed,em,eh,en,DOW(Monday bit0).
plc::Schedule evening{0,0,40,1,11,18,0,31,12,23,0,127};
plc::Schedule late{15,0,40,1,11,23,0,31,12,2,0,127};
void scan() {
    plc::output(0, plc::read_m(40));
    if (plc::input(0)) {
        evening.set_end_hour(22); // Changes schedule evaluation from next MAST.
    }
    if (plc::input(1)) {
        plc::write_system_word(114,0); // Disable all schedules from next MAST.
    }
}
