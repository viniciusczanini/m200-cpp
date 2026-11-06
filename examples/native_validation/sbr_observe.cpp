#include <plc.hpp>
// Authored probe text only; not compiled/generated/executed by this lane.
// I7 EXEC must go low until Q14=0 between transactions.
// I0 R, I1 CU, I2 CD, I3 seed bit0, I4 seed bit15, I5 seed bit14.
// I8 selects R-only partial block; otherwise R/CU/CD are all present.
plc::ShiftBitRegister sbr{0};
void scan() {
    if (plc::system(13)) {
        plc::write_m(900,false);
        plc::write_m(901,false);
        plc::write_word(15,0);
    }
    if (!plc::input(7)) plc::write_m(900,false);
    if (plc::input(7) && !plc::read_m(900)) {
        plc::write_m(900,true);
        if (plc::input(3)) sbr.set_bit(0,true);
        if (plc::input(4)) sbr.set_bit(15,true);
        if (plc::input(5)) sbr.set_bit(14,true);
        if (plc::input(8)) {
            sbr.update_pins(1,plc::input(0),false,false);
        } else {
            sbr.update(plc::input(0),plc::input(1),plc::input(2));
        }
        // All16 public BOOL operands, packed into an ordinary observation word.
        // MW0 is NOT an invented numeric %SBR0 operand. Signed i16 bit pattern.
        plc::write_word_bit(0,0,sbr.bit(0));
        plc::write_word_bit(0,1,sbr.bit(1));
        plc::write_word_bit(0,2,sbr.bit(2));
        plc::write_word_bit(0,3,sbr.bit(3));
        plc::write_word_bit(0,4,sbr.bit(4));
        plc::write_word_bit(0,5,sbr.bit(5));
        plc::write_word_bit(0,6,sbr.bit(6));
        plc::write_word_bit(0,7,sbr.bit(7));
        plc::write_word_bit(0,8,sbr.bit(8));
        plc::write_word_bit(0,9,sbr.bit(9));
        plc::write_word_bit(0,10,sbr.bit(10));
        plc::write_word_bit(0,11,sbr.bit(11));
        plc::write_word_bit(0,12,sbr.bit(12));
        plc::write_word_bit(0,13,sbr.bit(13));
        plc::write_word_bit(0,14,sbr.bit(14));
        plc::write_word_bit(0,15,sbr.bit(15));
        plc::write_word(1,0);
        plc::write_word_bit(1,0,plc::input(0));
        plc::write_word_bit(1,1,plc::input(1));
        plc::write_word_bit(1,2,plc::input(2));
        plc::write_word_bit(1,3,plc::input(3));
        plc::write_word_bit(1,4,plc::input(4));
        plc::write_word_bit(1,5,plc::input(5));
        plc::write_word_bit(1,8,plc::input(8));
        plc::inc_word(15);
        plc::write_m(901,true);
    }
    plc::output(0,sbr.bit(0));
    plc::output(1,sbr.bit(1));
    plc::output(2,sbr.bit(14));
    plc::output(3,sbr.bit(15));
    plc::output(14,plc::read_m(900));
    plc::output(15,plc::read_m(901));
}
