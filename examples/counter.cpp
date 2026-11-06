#include <plc.hpp>

plc::Counter items{0, 5};

void scan() {
    bool reached = items.update(plc::input(0), false,
                                plc::input(1), plc::input(2));
    plc::output(0, reached);
    plc::output(1, items.empty());
    plc::output(2, items.full());
    plc::output(3, items.value() > 0);
}
