// Memory-only controls M800..; indicators M704..M719; no source-level I/O.
#include <plc.hpp>

plc::i32 balances[4] = {1000, -2000, 3000, 4000};
plc::i16 batches = 0;

void scan() {
    if (plc::read_m(801)) {
        balances[0] = 1000;
        balances[1] = -2000;
        balances[2] = 3000;
        balances[3] = 4000;
        batches = 0;
    }
    if (plc::m_rising(800) && !plc::read_m(801) && batches < 3) {
        for (plc::i16 i = 0; i < 4; i = plc::add_i16(i, 1)) {
            plc::i32 weight = plc::int_to_dint(plc::add_i16(i, 1));
            balances[i] = plc::add_i32(balances[i], plc::mul_i32(weight, 250));
        }
        batches = plc::add_i16(batches, 1);
    }
    plc::i32 checksum = 0;
    for (plc::i16 i = 0; i < 4; i = plc::add_i16(i, 1)) {
        plc::i32 weight = plc::int_to_dint(plc::add_i16(i, 1));
        checksum = plc::add_i32(checksum, plc::mul_i32(balances[i], weight));
    }
    plc::write_dword(100, checksum);
    plc::write_word(102, batches);
    plc::write_dword(104, balances[0]);
    plc::write_dword(106, balances[3]);
    plc::write_m(704, checksum == 22000);
    plc::write_m(705, checksum == 29500);
    plc::write_m(706, checksum == 37000);
    plc::write_m(707, checksum == 44500);
    plc::write_m(708, batches == 0);
    plc::write_m(709, batches == 1);
    plc::write_m(710, batches == 2);
    plc::write_m(711, batches == 3);
    plc::i16 code = plc::low_word(plc::div_i32(checksum, 250));
    plc::write_m_bits_i16(712, 8, code);
}
