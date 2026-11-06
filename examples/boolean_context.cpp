#include <plc.hpp>

// Opt into native expression blocks. Requires native FL>=6.0 on export;
// official acceptance/save/reopen of this new path remains pending.
plc::BooleanContext context{true, true};

void scan() {
    plc::BooleanStack branches;
    branches.push(plc::input(0) && plc::input(1));
    plc::write_bit("%MW100:X15", branches.peek());
    plc::output(0, plc::rising(0, branches.pop()));
    plc::set_bit("%M100", plc::input_rising(2));
    plc::reset_bit("%M100", plc::input_falling(2));
    plc::output(1, plc::read_bit("%M100"));
}
