#include <plc.hpp>

void scan() {
    bool expression = plc::input(0) && plc::input(1);
    plc::output(0, plc::rising(0, expression));
    plc::output(1, plc::falling(0, expression));

    bool enabled_edge = false;
    if (plc::input(2)) {
        enabled_edge = plc::rising(1, plc::input(3));
    }
    plc::output(2, enabled_edge);
}
