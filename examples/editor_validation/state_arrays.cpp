#include <plc.hpp>

plc::i32 balances[4] = {1000, -2000, 3000, 4000};
plc::i16 batches = 0;

void scan() {
    if (plc::input(1)) {
        balances[0] = 1000;
        balances[1] = -2000;
        balances[2] = 3000;
        balances[3] = 4000;
        batches = 0;
    }
    if (plc::input_rising(0) && !plc::input(1) && batches < 3) {
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
    plc::output(0, checksum == 22000);
    plc::output(1, checksum == 29500);
    plc::output(2, checksum == 37000);
    plc::output(3, checksum == 44500);
    plc::output(4, batches == 0);
    plc::output(5, batches == 1);
    plc::output(6, batches == 2);
    plc::output(7, batches == 3);
    plc::i16 code = plc::low_word(plc::div_i32(checksum, 250));
    plc::write_output_bits_i16(8, 8, code);
}
