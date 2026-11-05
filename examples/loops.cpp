#include <plc.hpp>

void scan() {
    plc::i16 terms[2] = {3, 5};
    plc::i16 limit = terms[0];
    if (plc::input(0)) { limit = terms[1]; }
    plc::i16 sum = 0;
    for (plc::i16 i = 1; i <= limit; i = plc::add_i16(i, 1)) {
        sum = plc::add_i16(sum, i);
    }
    plc::write_word(20, sum);
    plc::output(0, sum == 15);
    plc::output(1, sum == 6);
}
