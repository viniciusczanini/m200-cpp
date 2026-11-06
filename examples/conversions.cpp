#include <plc.hpp>

void scan() {
    plc::i16 decimal = plc::bcd_to_int(9296); // BCD 0x2450 represents 2450.
    plc::i16 display = plc::int_to_bcd(decimal);
    plc::i32 long_decimal = plc::bcd_to_dint(-1717986919); // BCD 0x99999999.
    plc::i32 long_display = plc::dint_to_bcd(long_decimal);
    plc::i32 unsigned_word = plc::concat_words(-20536, 0); // Raw 0xAFC8 = 45000.
    plc::i32 signed_word = plc::int_to_dint(-20536); // Local DWORD sign policy.
    plc::output(0, decimal == 2450 && display == 9296);
    plc::output(1, long_decimal == 99999999 && long_display == -1717986919);
    plc::output(2, unsigned_word == 45000 && signed_word == -20536);
    plc::output(3, !plc::system(18));
}
