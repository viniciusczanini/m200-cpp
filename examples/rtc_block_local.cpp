#include <plc.hpp>

// SDK/IR/VM/reverse only: RTC_EXEC native IL/Ladder binding is explicitly gated.
plc::Rtc clock0{0,29,2,2028,12,0,0};
void scan() {
    clock0.update(true,plc::input(0),plc::input(1));
    plc::output(0,clock0.done());
    plc::output(1,clock0.error());
    plc::write_word(10,clock0.error_id());
    plc::write_word(11,clock0.day_of_week());
}
