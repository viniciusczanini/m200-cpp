// Memory-only controls M800..; indicators M704..M719; no source-level I/O.
#include <plc.hpp>

plc::Ton ready{0, 100, 5};
plc::Counter accepted{0, 3};
bool latched = false;

void scan() {
    bool qualified = ready.update(plc::read_m(801) && !plc::read_m(802));
    bool pulse = plc::m_rising(800);
    bool complete = accepted.update(plc::read_m(802), false, pulse && qualified, false);
    if (plc::read_m(802)) { latched = false; }
    if (complete) { latched = true; }
    plc::i16 latch_word = 0;
    if (latched) { latch_word = 1; }
    plc::write_word(120, accepted.value());
    plc::write_word(121, ready.value());
    plc::write_word(122, ready.preset());
    plc::write_word(123, accepted.preset());
    plc::write_word(124, latch_word);
    plc::write_m(704, qualified);
    plc::write_m(705, accepted.value() == 1);
    plc::write_m(706, accepted.value() == 2);
    plc::write_m(707, complete);
    plc::write_m(708, latched);
    plc::write_m(709, accepted.value() == 0);
    plc::write_m(710, plc::read_m(801));
    plc::write_m(711, plc::read_m(802));
    plc::write_m_bits_i16(712, 4, accepted.value());
    plc::write_m(716, ready.value() > 0);
    plc::write_m(717, accepted.preset() == 3);
    plc::write_m(718, ready.preset() == 5);
    plc::write_m(719, !plc::system(18) && !plc::system(20));
}
