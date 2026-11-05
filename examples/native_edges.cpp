#include <plc.hpp>

void scan() {
    plc::output(0, plc::input_rising(0));
    plc::output(1, plc::input_falling(0));
    plc::write_m(100, plc::input(0));
    // M edges observe scan-boundary changes, including writes from last scan.
    plc::output(2, plc::m_rising(100));
    plc::output(3, plc::m_falling(100));
    plc::output(4, plc::input_rising(23));
}
